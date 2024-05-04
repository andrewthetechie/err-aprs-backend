import sys

from aprs_backend.message import APRSMessage
from aprs_backend.clients import APRSISClient
from aprs_backend.person import APRSPerson
from aprs_backend.room import APRSRoom
from aprs_backend.version import __version__ as ERR_APRS_VERSION
from errbot.backends.base import Message
from errbot.backends.base import ONLINE
from errbot.core import ErrBot
from aprs_backend.exceptions import ProcessorError, PacketParseError, APRSISConnnectError
from aprs_backend.packets.parser import parse, hash_packet
from expiringdict import ExpiringDict
from functools import cached_property
from aprs_backend.packets import AckPacket, RejectPacket, MessagePacket
from aprs_backend.utils.counter import MessageCounter
from random import randint
from datetime import datetime
from better_profanity import profanity
from aprs_backend.clients.aprs_registry import APRSRegistryClient, RegistryAppConfig
import logging
import asyncio
from errbot.version import VERSION as ERR_VERSION


log = logging.getLogger(__name__)

for handler in log.handlers:
    handler.setFormatter(
        logging.Formatter("%(filename)s: " "%(levelname)s: " "%(funcName)s(): " "%(lineno)d:\t" "%(message)s")
    )


class APRSBackend(ErrBot):
    def __init__(self, config):
        log.debug("Initied")

        self._errbot_config = config
        aprs_config = {"host": "rotate.aprs.net", "port": 14580}
        aprs_config.update(config.BOT_IDENTITY)

        self._sender_config = {}

        if "callsign" not in aprs_config:
            log.fatal("No callsign in bot identity")
            sys.exit(1)
        if "password" not in aprs_config:
            log.fatal("No password in bot identity")
            sys.exit(1)

        self.callsign = aprs_config["callsign"]
        self.from_call = self._get_from_config("APRS_FROM_CALLSIGN", self.callsign)
        self.listened_callsigns = self._get_from_config("APRS_LISTENED_CALLSIGNS", ())
        self.bot_identifier = APRSPerson(self.callsign)
        self._multiline = False
        self._client = APRSISClient(**aprs_config, logger=log)
        self._send_queue = asyncio.Queue(maxsize=int(self._get_from_config("APRS_SEND_MAX_QUEUE", "2048")))
        self.help_text = self._get_from_config("APRS_HELP_TEXT", "APRSBot,Errbot & err-aprs-backend")

        self._message_counter = MessageCounter(initial_value=randint(1, 20))  # nosec not used cryptographically
        self._max_dropped_packets = int(self._get_from_config("APRS_MAX_DROPPED_PACKETS", "25"))
        self._max_cached_packets = int(self._get_from_config("APRS_MAX_CACHED_PACKETS", "2048"))
        self._message_max_retry = int(self._get_from_config("APRS_MESSAGE_MAX_RETRIES", "7"))
        self._message_retry_wait = int(self._get_from_config("APRS_MESSAGE_RETRY_WAIT", "90"))

        # strip newlines out of plugin responses before sending to aprs, probably best to leave it true, nothing in aprs will handle
        # a stray newline
        self._strip_newlines = str(self._get_from_config("APRS_STRIP_NEWLINES", "true")).lower() == "true"

        # try to strip out "foul" language the FCC would not like. It is possible/probably an errbot bot response could
        # go out over the airwaves. This is configurable, but probably should remain on.
        self._language_filter = str(self._get_from_config("APRS_LANGUAGE_FILTER", "true")).lower() == "true"
        if self._language_filter:
            profanity.load_censor_words(self._get_from_config("APRS_LANGUAGE_FILTER_EXTRA_WORDS", []))

        self._max_age_cached_packets_seconds = int(self._get_from_config("APRS_MAX_AGE_CACHED_PACETS_SECONDS", "3600"))
        self._packet_cache = ExpiringDict(
            max_len=self._max_cached_packets, max_age_seconds=self._max_age_cached_packets_seconds
        )
        self._packet_cache_lock = asyncio.Lock()
        self._waiting_ack = ExpiringDict(
            max_len=self._max_cached_packets, max_age_seconds=self._max_age_cached_packets_seconds
        )
        self._waiting_ack_lock = asyncio.Lock()

        self.registry_enabled = self._get_from_config("APRS_REGISTRY_ENABLED", "false").lower() == "true"
        if self.registry_enabled:
            self.registry_app_config = RegistryAppConfig(
                description=self._get_from_config("APRS_REGISTRY_DESCRIPTION", "err-aprs-backend powered bot"),
                website=self._get_from_config("APRS_REGISTRY_WEBSITE", ""),
                listening_callsigns=[self.from_call] + [call for call in self.listened_callsigns],
                software=self._get_from_config(
                    "APRS_REGISTRY_SOFTWARE", f"err-aprs-backend {ERR_APRS_VERSION} errbot {ERR_VERSION}"
                ),
            )
            if (registry_software := self._get_from_config("APRS_REGISTRY_SOFTWARE", None)) is not None:
                self.registry_app_config.software = registry_software
            self.registry_client = APRSRegistryClient(
                registry_url=self._get_from_config("APRS_REGISTRY_URL", "https://aprs.hemna.com/api/v1/registry"),
                log=log,
                frequency_seconds=int(self._get_from_config("APRS_REGISTRY_FREQUENCY_SECONDS", "3600")),
                app_config=self.registry_app_config,
            )
        else:
            self.registry_client = None

        super().__init__(config)

    def _get_from_config(self, key: str, default: any = None) -> any:
        return getattr(self._errbot_config, key, default)

    def build_reply(self, msg: Message, text: str, private: bool = False, threaded: bool = False) -> Message:
        log.debug(msg)
        reply = Message(
            body=text,
            to=msg.frm,
            frm=self.bot_identifier,
            extras={
                "msg_number": msg.extras["msgNo"],
                "via": msg.extras["via"],
                "path": msg.extras["path"],
                "raw": msg.extras["raw"],
                "packet": msg.extras["packet"],
            },
        )
        return reply

    def set_message_size_limit(self, limit=64, hard_limit=67):
        """
        APRS supports upto 67 characters per message
        http://www.aprs.org/txt/messages.txt
        """
        super().set_message_size_limit(limit, hard_limit)

    def warn_admins(self, warning: str) -> None:
        """
        Send a warning to the administrators of the bot.
        For APRS this is too spammy over the airwaves, only log admin warnings to
        the bots log at a warning level

        :param warning: The markdown-formatted text of the message to send.
        """
        log.warning(warning)

    async def retry_worker(self) -> None:
        """Processes self._waiting_ack for messages we've sent that have not been acked

        Will resend a message up to APRS_MESSAGE_MAX_RETRIES number of tries while waiting
        at least APRS_MESSAGE_RETRY_WAIT seconds between retries
        """
        log.debug("retry_worker started")
        while True:
            async with self._waiting_ack_lock:
                current_keys = self._waiting_ack.keys()
            for key in current_keys:
                async with self._waiting_ack_lock:
                    this_packet = self._waiting_ack.get(key, None)

                # packet will be none if this packet has expired or been ack'd or
                # rejected in between us pulling keys and getting it
                if this_packet is None:
                    continue

                # check max retries first, its cheaper than a timedelta
                if this_packet.last_send_attempt > self._message_max_retry:
                    log.debug("Packet %s over max retries, dropping %s", key, this_packet.json)
                    await self.__drop_message_from_waiting(key)
                    continue

                # if this packet has not been sent in self._message_retry_wait seconds, resent it
                # it hasn't been ack'd yet
                if (datetime.now() - this_packet.last_send_time).total_seconds() > self._message_retry_wait:
                    log.debug("Message %s needs to be re-sent %s", key, this_packet.json)
                    self.send_message(APRSMessage.from_message_packet(this_packet))
                # release the loop for a bit
                await asyncio.sleep(0.01)
            # release the loop for a bit longer after we've gone through all keys
            await asyncio.sleep(0.1)

    async def send_worker(self) -> None:
        """Processes self._send_queue to send messages to APRS"""
        log.debug("send_worker started")
        while True:
            try:
                packet = self._send_queue.get_nowait()
            except asyncio.QueueEmpty:
                packet = None
            if packet is not None:
                log.debug("send_worker got Packet %s", packet.json)
                await packet.prepare(self._message_counter)
                packet.update_timestamp()
                await self._client._send(packet.raw)
                packet.last_send_time = datetime.now()
                packet.last_send_attempt += 1
                async with self._waiting_ack_lock:
                    self._waiting_ack[hash_packet(packet)] = packet
                self._send_queue.task_done()
            # release the loop for a bit
            await asyncio.sleep(0.01)

    async def receive_worker(self) -> bool:
        """_summary_"""
        log.debug("Receive worker started")
        try:
            await self._client.connect()
        except APRSISConnnectError as exc:
            log.error(exc)
            return False

        self._dropped_packets = 0
        try:
            while True:
                packet_str = await self._client.get_packet()
                # check if this is just a status keepalive from the aprs server
                # or connetion replies info.
                # They all startwith "# "
                if packet_str.startswith("# "):
                    log.debug("Status message from aprs server: %s", packet_str)
                    continue
                try:
                    parsed_packet = parse(packet_str)
                    # release the loop for a bit
                    await asyncio.sleep(0.01)
                    if parsed_packet is not None:
                        if parsed_packet.to == self.callsign or parsed_packet.to in self.listened_callsigns:
                            await self.process_packet(parsed_packet)
                        else:
                            log.info(
                                "Packet was not addressed to bot or listened callsigns, not processing %s", packet_str
                            )
                    else:
                        log.info("This packet parsed to be None: %s", packet_str)
                except PacketParseError as exc:
                    log.error(
                        "Dropping packet %s due to Parsing error: %s. Total Dropped Packets: %s",
                        packet_str,
                        exc,
                        self._dropped_packets,
                    )
                except ProcessorError as exc:
                    log.err(
                        "Dropping packet %s due to Processor error: %s. Total Dropped Packets: %s",
                        packet_str,
                        exc,
                        self._dropped_packets,
                    )
                finally:
                    self._dropped_packets += 1
                    if self._dropped_packets > self._max_dropped_packets:
                        return False
        except KeyboardInterrupt:
            log.info("Interrupt received, shutting down..")
            return True
        except Exception as exc:
            log.error("Fatal unhandled error reading from APRS %s", exc)
            return False

    async def async_serve_once(self) -> bool:
        receive_task = asyncio.create_task(self.receive_worker())

        worker_tasks = [asyncio.create_task(self.send_worker()), asyncio.create_task(self.retry_worker())]
        # if reporting to the aprs service registry is enabled, start a task for it
        if self.registry_client is not None:
            worker_tasks.append(asyncio.create_task(self.registry_client()))
        result = await asyncio.gather(receive_task, return_exceptions=True)
        await self._send_queue.join()
        for task in worker_tasks:
            task.cancel()
        return result

    def serve_once(self) -> bool:
        self.connect_callback()
        try:
            return asyncio.run(self.async_serve_once())
        except Exception as exc:
            log.error("Unhandled exception in AIO routine %s", exc)
            return False
        finally:
            log.debug("Triggering disconnect callback in sync serve_once")
            self.disconnect_callback()

    def build_identifier(self, txtrep: str) -> None:
        return APRSPerson(callsign=txtrep)

    def change_presence(self, status: str = ONLINE, message: str = "") -> None:
        return None

    def send_message(self, msg: Message) -> None:
        log.debug("Sending %s", msg)
        super().send_message(msg)

        msg_text = msg.body
        if self._strip_newlines:
            msg_text = msg_text.strip("\n").strip("\r").strip("\t")
        if self._language_filter:
            msg_text = profanity.censor(msg_text)
        msgNo = None
        last_send_attempt = 0
        if "packet" in msg.extras:
            msgNo = getattr(msg.extras["packet"], "msgNo", None)
            last_send_attempt = getattr(msg.extras["packet"], "last_send_attempt", 0)
        if msgNo is None:
            msgNo = self._message_counter.get_value_sync()
        msg_packet = MessagePacket(
            from_call=self.from_call,
            to_call=msg.to.callsign,
            addresse=msg.to.callsign,
            message_text=msg_text,
            msgNo=msgNo,
            last_send_attempt=last_send_attempt,
        )
        msg_packet._build_raw()
        try:
            self._send_queue.put_nowait(msg_packet)
            log.debug("Packet %s put in send queue", msg_packet.json)
        except asyncio.QueueFull:
            log.error("Send queue is full, can't send msg %s", msg)
            self._dropped_packets += 1

    @property
    def mode(self) -> str:
        return "aprs"

    @cached_property
    def _lowered_callsign(self):
        return self.callsign.lower()

    def query_room(self, _: str) -> APRSRoom:
        """Room can either be a name or a channelid"""
        return APRSRoom("aprs")

    def rooms(self) -> list[APRSRoom]:
        """
        Return a list of rooms the bot is currently in.
        """
        return [APRSRoom("aprs")]

    async def process_packet(self, packet: AckPacket | RejectPacket | MessagePacket) -> None:
        log.debug("Processing packet %s", packet.json)
        if isinstance(packet, MessagePacket):
            await self._process_message(packet)
        elif isinstance(packet, AckPacket) or isinstance(packet, RejectPacket):
            await self._process_ack_rej(packet)

    async def _process_ack_rej(self, packet: dict[str, str | bool]) -> None:
        """
        Process an ack or reject packet by checking if its in the messages
        waiting for an ack and if so, remove it the message
        """
        # Remove this message from our sent messages that are waiting for acks
        await self.__drop_message_from_waiting(hash_packet(packet))

    async def __drop_message_from_waiting(self, message_hash: str) -> None:
        """Gets the waiting_ack_lock and deletes a message from _waiting_ack if it exists"""
        async with self._waiting_ack_lock:
            try:
                self._waiting_ack.pop(message_hash)
            except KeyError:
                pass

    def handle_help(self, msg: APRSMessage) -> None:
        """Returns simplified help text for the APRS backend"""
        help_msg = APRSMessage(body=self.help_text, extras=msg.extras)
        help_msg.to = msg.frm
        help_msg.frm = APRSPerson(callsign=self.from_call)
        self.send_message(help_msg)

    async def _process_message(self, packet: MessagePacket) -> None:
        """
        Check if this message is a dupe of one the bot is already processing
        (waiting for an ack), and dispatch it to plugins
        """
        log.debug(packet.raw_dict)
        # send an ack to this message
        await self._ack_message(packet)
        this_packet_hash = hash_packet(packet)
        async with self._packet_cache_lock:
            if self._packet_cache.get(this_packet_hash, None) is not None:
                log.info("Duplicate packet %s. Skipping processing", packet.json)
                return
            self._packet_cache[this_packet_hash] = packet
        msg = APRSMessage.from_message_packet(packet)
        if msg.body.lower().strip(" ").strip("\n").strip("\r") == "help":
            return self.handle_help(msg)
        return self.callback_message(msg)

    async def _ack_message(self, packet: MessagePacket) -> None:
        log.debug("Sending ack for packet %s", packet.json)
        this_ack = AckPacket(
            from_call=self.from_call, to_call=packet.from_call, addresse=packet.from_call, msgNo=packet.msgNo
        )
        await this_ack.prepare(self._message_counter)
        this_ack.update_timestamp()
        await self._client._send(this_ack.raw)
        return
