from errbot.backends.base import (
    ONLINE,
    Message,
)
from errbot.core import ErrBot
from aprsd.packets import core



import sys


from queue import Queue


from aprs_backend.utils.log import log

from aprs_backend.clients import ErrbotAPRSISClient
from aprs_backend.threads.rx import ErrbotRXThread
from aprs_backend.threads.tx import ErrbotAPRSSender


from aprs_backend.room import APRSRoom
from aprs_backend.person import APRSPerson
from aprs_backend.packets.list import ErrbotPacketList
from aprs_backend.packets.tracker import ErrbotPacketTrack
from aprs_backend.packets.seen import ErrbotPacketsSeenList
import os
from aprs_backend.threads.processor import PacketProcessorThread


class APRSBackend(ErrBot):
    def __init__(self, config):
        log.debug("Initied")
        
        aprs_config = {
            "host": "rotate.aprs.net",
            "port": 14580
        }
        aprs_config.update(config.BOT_IDENTITY)

        sender_config = {}
        if getattr(config, "APRS_MSG_RATE_LIMIT_PERIOD", None) is not None:
            sender_config['msg_rate_limit_period'] = getattr(config, "APRS_MSG_RATE_LIMIT_PERIOD")
        if getattr(config, "APRS_ACK_RATE_LIMIT_PERIOD", None) is not None:
            sender_config['ack_rate_limit_period'] = getattr(config, 'APRS_ACK_RATE_LIMIT_PERIOD')

        if 'callsign' not in aprs_config:
            log.fatal("No callsign in bot identity")
            sys.exit(1)
        if 'password' not in aprs_config:
            log.fatal("No password in bot identity")
            sys.exit(1)

        self.callsign = aprs_config['callsign']
        self.bot_identifier = APRSPerson(self.callsign)
        self._multiline = False

        packet_storage_kwargs = {}

        for kwarg, config_key in {
            "enable_save": "APRS_PACKET_STORE_ENABLE_SAVE",
            "save_location": "APRS_PACKET_STORE_SAVE_LOCATION",
            "aprs_packet_store_filename_prefix": "APRS_PACKET_STORE_FILENAME_PREFIX",
            "aprs_packet_store_filename_suffix": "APRS_PACKET_STORE_FILENAME_SUFFIX",
            "aprs_packet_store_file_extension": "APRS_PACKET_STORE_FILE_EXTENSION"
        }.items():
            if (config_val := getattr(config, config_key, None)) is not None:
                packet_storage_kwargs[kwarg] = config_val
        if 'save_location' not in packet_storage_kwargs:
            packet_storage_kwargs['save_location'] = config.BOT_DATA_DIR + "/aprsb"
        if not os.path.exists(packet_storage_kwargs['save_location']):
            os.makedirs(packet_storage_kwargs['save_location'])

        self.packet_list = ErrbotPacketList()
        self.packet_tracker = ErrbotPacketTrack()
        self.packet_tracker.configure(**packet_storage_kwargs)
        self.seen_list = ErrbotPacketsSeenList()
        self.seen_list.configure(**packet_storage_kwargs)
        if str(getattr(config, "APRS_FLUSH_PACKET_TRACKERS", False)).lower() == "true":
            self.packet_tracker.flush()
            self.seen_list.flush()
        else:
            self.packet_tracker.load()
            self.seen_list.load()

        self._rx_queue = Queue()
        self._aprs_client = ErrbotAPRSISClient()
        self._aprs_client.setup_connection(self.callsign, 
                                           aprs_config['password'], 
                                           host=aprs_config['host'], 
                                           port=aprs_config['port'])
        self.threads = {}
        self.threads['rx'] = ErrbotRXThread(packet_queue=self._rx_queue, client=self._aprs_client)
        self.threads['sender'] = ErrbotAPRSSender(client=self._aprs_client, config=sender_config) 
        self.threads['processor'] = PacketProcessorThread(callsign=self.callsign,
                                                         packet_queue=self._rx_queue,
                                                         packet_tracker=self.packet_tracker,
                                                         backend_callback=self.callback_message)
        super().__init__(config)

    def build_reply(self, msg: Message, text: str, private: bool = False, threaded: bool = False) -> Message:
        msg = Message(
            body=text,
            to=msg.frm,
            frm=self.bot_identifier,
            extras = {
                "msg_number": msg.extras['msg_number'],
                "via": msg.extras['via'],
                "path": msg.extras['path'],
                "raw": msg.extras['raw'],
                "packet": msg.extras['packet']
            }
        )
        return msg

    def set_message_size_limit(self, limit=67, hard_limit=67):
        """
        APRS supports upto 67 characters per message
        http://www.aprs.org/txt/messages.txt
        """
        super().set_message_size_limit(limit, hard_limit)

    def shutdown(self):
        for key, thread in self.threads.items():
            log.debug("Stopping %s thread", key)
            thread.stop()
        self.packet_tracker.save()
        self.seen_list.save()
        super().shutdown()

    def disconnect_callback(self):
        pass

    def callback_message(self, msg: Message) -> None:
        log.debug("Recieved msg %s", msg)
        super().callback_message(msg)

    def serve_once(self):
        log.debug("APRS backend started")
        self.connect_callback()
        try:
            for key, thread in self.threads.items():
                log.debug("Starting %s thread", key)
                thread.start()
            self.packet_tracker.restart()
            for key, thread in self.threads.items():
                log.debug("Joining %s thread", key)
                thread.join()
        except KeyboardInterrupt:
            log.info("Interrupt received, shutting down..")
            return True
        except Exception as exc:
            log.exception("Error reading from APRS")
            log.exception(exc)
        finally:
            log.debug("Triggering disconnect callback")
            self.disconnect_callback()

    def build_identifier(self, txtrep: str) -> None:
        """
        """
        return None

    def change_presence(self, status: str = ONLINE, message: str = "") -> None:
        return None
 
    def send_message(self, msg: Message) -> None:
        super().send_message(msg)
        packet = core.MessagePacket(
            from_call=self.callsign,
            to_call=msg.to.callsign,
            addresse=msg.to.callsign,
            message_text=msg.body
        )
        packet._build_raw()
        self.threads['sender'].send(packet)


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