import sys

from aprs_backend.person import APRSPerson
from aprs_backend.room import APRSRoom
from aprs_backend.message import APRSMessage
from aprs_backend.parser.ackrej import parse_ack_rej_msg_id, parse_new_ackrej_format
from errbot.backends.base import ONLINE
from errbot.core import ErrBot
from expiringdict import ExpiringDict
import os
from aprs_backend.util.message import get_message_hash

from functools import cached_property
from pathlib import Path

import logging
import aprslib
import pickle


log = logging.getLogger(__name__)

class APRSBackend(ErrBot):
    def __init__(self, config):
        log.debug("Initied")

        self._errbot_config = config

        aprs_config = {"host": "rotate.aprs.net", "port": 14580}
        aprs_config.update(config.BOT_IDENTITY)

        self._aprs_config = aprs_config
        if "callsign" not in aprs_config:
            log.fatal("No callsign in bot identity")
            sys.exit(1)
        if "password" not in aprs_config:
            log.fatal("No password in bot identity")
            sys.exit(1)

        self._packet_cache_config = {
            "enable_save": getattr(self._errbot_config, "APRS_PACKET_CACHE_ENABLE_SAVE", "False").lower() == "true",
            "purge": getattr(self._errbot_config, "APRS_PACKET_CACHE_PURGE", "False").lower() == "true",
            "save_location": getattr(self._errbot_config, "APRS_PACKET_CACHE_SAVE_LOCATION", f"{config.BOT_DATA_DIR}/aprsb"),
            "filename_prefix": getattr(self._errbot_config, "APRS_PACKET_CACHE_FILENAME_PREFIX", ""),
            "filename_suffix": getattr(self._errbot_config, "APRS_PACKET_CACHE_FILENAME_SUFFIX", ""),
            "file_extension": getattr(self._errbot_config, "APRS_PACKET_CACHE_FILE_EXTENSION", ".p"),
            "ttl": int(getattr(self._errbot_config, "APRS_PACKET_CACHE_TTL_SECONDS", 30 * 60)),
            "cache_size": int(getattr(self._errbot_config, "APRS_PACKET_CACHE_MAX_ENTRIES", 2160))
        }
        if not self._packet_cache_config['file_extension'].startswith("."):
            self._packet_cache_config['file_extension'] = f".{self._packet_cache_config['file_extension']}"

        self.callsign = aprs_config["callsign"]
        self.to_call = getattr(self._errbot_config, "APRS_TOCALL", "APERRB")
        self.monitored_callsigns = [self.callsign] + getattr(config, "APRS_ADDITIONAL_CALLSIGNS", [])
        self.bot_identifier = APRSPerson(self.callsign)
        self._multiline = False
        self._AIS = aprslib.IS(
            self.callsign, self._aprs_config['password']
        )
        self._AIS.set_server(self._aprs_config['host'], self._aprs_config['port'])
        self._aprs_filter = getattr(self._errbot_config, "APRS_FILTER_OVERRIDE", f"g/{self.callsign}")
        self._AIS.set_filter(self._aprs_filter)

        self._aprs_msg_cache = self._get_message_cache()
        super().__init__(config)

    def _get_message_cache(self):
        to_return = ExpiringDict(max_len=self._packet_cache_config['cache_size'], max_age_seconds=self._packet_cache_config['ttl'])
        if not self._packet_cache_config['enable_save']:
            return to_return

        if self._packet_cache_config['purge']:
            self._cleanup_packet_cache_on_disk(self)
            return to_return

        loaded = self._load_packet_pack_from_disk(self)
        return to_return if loaded is None else loaded

    def _save_message_cache(self):
        if self._packet_cache_config['enable_save']:
            try:
                with open(self._packet_cache_path, 'wb') as fh:
                    pickle.dump(self._aprs_msg_cache, fh)
            except Exception as exc:
                log.error("Error while saving message cache to %s - %x. Message cache unsaved", self._packet_cache_path, exc)

    @cached_property
    def _packet_cache_path(self):
        filename = f"{self._packet_cache_config['filename_prefix']}packetcache{self._packet_cache_config['filename_suffix']}{self._packet_cache_config['file_extension']}"
        return Path(self._packet_cache_config['save_location']) / filename

    def _cleanup_packet_cache_on_disk(self) -> None:
        """Deletes packet cache files from disk"""
        if self._packet_cache_path.exists():
            try:
                os.remove(self._packet_cache_path)
            except Exception as exc:
                log.error("Error while cleaning up packet cace at %s - %s", self._packet_cache_path, exc)

    def _load_packet_pack_from_disk(self):
        # pickle is bad news, need to figure out a safer, better way of doing this
        # but this is good enough for a proof of concept
        to_return = None
        if self._packet_cache_path.exists():
            try:
                with open(self._packet_cache_path, 'rb') as fh:
                    to_return = pickle.load(fh)
            except Exception as exc:
                log.error("Error while loading from %s. %s", self._packet_cache_config, exc)
        return to_return

    def build_reply(
        self, msg: APRSMessage, text: str, private: bool = False, threaded: bool = False
    ) -> APRSMessage:
        log.debug(msg)
        reply = APRSMessage(
            body=text,
            to=msg.frm,
            frm=self.bot_identifier,
            extras={
                "msg_number": msg.extras["msg_number"],
                "via": msg.extras["via"],
                "path": msg.extras["path"],
                "raw": msg.extras["raw"],
                "packet": msg.extras["packet"],
            },
        )
        log.debug(reply)
        return reply

    def set_message_size_limit(self, limit=64, hard_limit=67):
        """
        APRS supports upto 67 characters per message
        http://www.aprs.org/txt/messages.txt
        """
        super().set_message_size_limit(limit, hard_limit)

    def shutdown(self):
        self._save_message_cache()
        super().shutdown()

    def disconnect_callback(self):
        pass

    def callback_message(self, msg: APRSMessage) -> None:
        log.debug("Recieved msg %s", msg)
        super().callback_message(msg)

    def aprs_callback(self, raw_aprs_packet: dict):
        """APRS Lib callback that processes an APRS packet and turns it into a message that Errbot can handle

        Calls callback_message"""
        log.debug(raw_aprs_packet)

        # Extract base data from the APRS message
        # the APRS-IS filter should guarantee that we have received an APRS message
        # If one of these fields cannot be extracted (or is not present, e.g. msgno), then set it to none

        # addresse contains the APRS id that the user has sent the data to
        # Usually, this is our callsign but could also be other callsigns if there is a user provided filter
        addresse = raw_aprs_packet.get("addresse", None)

        if addresse is None:
            log.info("Packet has no address, skipping")
            return

        if addresse not in self.monitored_callsigns:
            log.info("Packet not addressed to one of our monitored callsigns. Dropping")
            return

        # Sender's call sign. read: who has sent us this message?
        from_callsign: str | None = raw_aprs_packet.get("from", None)
        if from_callsign is None:
            log.error("Malformed packet, no from_callsign. Skipping")
            return
        from_callsign: str = from_callsign.upper()

        # Text of the message sent to us
        message_text: str | None = raw_aprs_packet.get("message_text", None)

        # messagenumber, if present in the original msg
        # msg_number is optional
        msg_number: str | None = raw_aprs_packet.get("msgNo", None)

        # flag to indicate if this is a new style ackrej format. We'll evaluate this as we parse the packet
        is_new_ackrej_packet: bool = False
        # message response, indicating a potential ack/rej
        response = raw_aprs_packet.get("response", None)
        if response:
            response = response.lower()

        # Get the format of the packet
        # Note that APRSlib DOES return ack/rej messages as format type "message".
        # however, the message text is empty for such cases
        packet_format = raw_aprs_packet.get("format", None)

        # Check if this packet is in the new ack-rej format
        # arpslib cannot handle these messages properly so we have to apply a workaround
        # Both 'sender_message_id' and 'our_old_message_id' are not needed
        # as we don't resubmit data in case it hasn't been received
        if packet_format == "message" and message_text is not None:
            message_text, response, sender_message_id, our_old_message_id = parse_ack_rej_msg_id(message_text)

        # This is a special handler for the new(er) APRS ack/rej/format
        # By default (and described in aprs101.pdf pg. 71), APRS supports two
        # messages:
        # - messages withOUT message ID, e.g. Hello World
        # - message WITH 5-character message ID, e.g. Hello World{12345
        # The latter require the program to send a seperate ACK to the original
        # recipient
        #
        # Introduced through an addendum (http://www.aprs.org/aprs11/replyacks.txt),
        # a third option came into place. This message also has a message ID but
        # instead of sending a separate ACK, the original message ID is returned to
        # the user for all messages that relate to the original one. aprslib does
        # currently not recognise these new message IDs - therefore, we need to
        # extract them from the message text and switch the program logic if we
        # discover that new ID.
        if msg_number is None and message_text is not None:
            message_text, msg_number, is_new_ackrej_packet = parse_new_ackrej_format(message_text)

        # At this point in time, we have successfully removed any potential trailing
        # information from the message string and have assigned it to e.g. message ID
        # etc. This means that both message and message ID (whereas present) do now
        # qualify for dupe checks - which will happen at a later point in time
        # Any potential (additional) message retry information is no longer present
        #
        # Based on whether we have received a message number, we now set a session
        # parameter for this message whether an ACK is required
        # and whether we are supposed to send outgoing messages with or without
        # that message number.
        # True = Send ack for initial message, enrich every outgoing msg with msgno
        msg_no_supported = msg_number is not None

        if message_text is None:
            log.info("Packet has no message text. Skipping")
            return

        if response in ['ack', 'rej']:
            log.info("Packet is an ack or a rej, skipping.")
            return

        # If the packet has made it this far, then it is a message packet, addressed to the bot
        # and isn't malformed. Now, check if its a duplicate message.
        message_hash = get_message_hash(message_text=message_text, message_number=msg_number, sender_callsign=from_callsign)
        if message_hash in self._aprs_msg_cache:
            log.info("Duplicated packet, message still in decaying message cache %s", message_hash)
            return

        # Not a duplicate message, let's check if we need to send an ack

        # Send an ack if we DID receive a message number
        # and we DID NOT have received a request in the
        # new ack/rej format
        # see aprs101.pdf pg. 71ff.
        if msg_no_supported and not is_new_ackrej_packet:
            self.send_ack(to_callsign=from_callsign, src_msg_number=msg_number)

        # now put together an errbot message and trigger the errbot message callback
        msg = APRSMessage(
            body=message_text,
            extras={
                "msg_number": msg_number,
                "via": raw_aprs_packet.get("via", None),
                "path": raw_aprs_packet.get("path", None),
                "raw": raw_aprs_packet.get("raw", "None"),
                "packet": raw_aprs_packet,
            },
        )
        msg.frm = APRSPerson(callsign=from_callsign)
        msg.to = APRSPerson(self.callsign)
        self.callback_message(msg)


    def send_ack(self, to_callsign: str, src_msg_number: str) -> None:
        """Send an ACK packet to to_callsign"""
        to_send = f"{self.callsign}>{self.to_call}::{to_callsign}:ack{src_msg_number}"
        log.debug("Sending ACK %s", to_send)
        self.send_string_to_aprs(to_send=to_send)


    def send_string_to_aprs(self, to_send: str) -> None:
        self._AIS.sendall(to_send)

    def serve_once(self):
        log.debug("APRS backend started")
        try:
            self._AIS.connect(blocking=True)
            if self._AIS._connected:
                log.info(msg="Established the connection to APRS_IS")
                log.info(msg="Starting callback consumer")
                self._AIS.consumer(self.aprs_callback, blocking=True, immortal=True, raw=False)
                # we've left the consumer, which means that APRS connection has dropped
                log.info("CLosing connection to APRS-IS")
                self._AIS.close()
            else:
                log.error("Cannot establish connection to APRS IS")
        except (KeyboardInterrupt, SystemExit) as exc:
            log.info("Recieved %s. Stopping", exc)
            if self._AIS:
                self._AIS.close()

    def build_identifier(self, txtrep: str) -> None:
        """ """
        return None

    def change_presence(self, status: str = ONLINE, message: str = "") -> None:
        return None

    def send_message(self, msg: APRSMessage) -> None:
        super().send_message(msg)
        log.debug("Sending %s", msg)
        # TODO: Write sender


    @property
    def mode(self) -> str:
        return "aprs"

    def query_room(self, _: str) -> APRSRoom:
        """Room can either be a name or a channelid"""
        return APRSRoom("aprs")

    def rooms(self) -> list[APRSRoom]:
        """
        Return a list of rooms the bot is currently in.
        """
        return [APRSRoom("aprs")]
