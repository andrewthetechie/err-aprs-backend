import logging
import queue
from collections.abc import Callable

from aprs_backend.message import APRSMessage
from aprs_backend.packets.tracker import ErrbotPacketTrack
from aprs_backend.person import APRSPerson
from aprs_backend.threads import ErrbotAPRSDThread
from aprs_backend.threads.tx import send_via_queue
from aprsd import packets
from aprsd.packets import core

log = logging.getLogger(__name__)


class PacketProcessorThread(ErrbotAPRSDThread):
    """Thread that sends a GPS beacon packet periodically.

    Settings are in the [DEFAULT] section of the config file.
    """

    _loop_cnt: float = 1

    def __init__(
        self,
        callsign: str,
        packet_queue: queue.Queue,
        packet_tracker: ErrbotPacketTrack,
        backend_callback: Callable,
    ):
        super().__init__("PacketProcessorThread")
        self.callsign = callsign
        self.packet_queue = packet_queue
        self.packet_tracker = packet_tracker
        self.backend_callback = backend_callback
        self._loop_cnt = 1

    def loop(self):
        try:
            packet = self.packet_queue.get(timeout=0.25)
            if packet:
                self.process_packet(packet)
        except queue.Empty:
            pass
        self._loop_cnt += 1
        return True

    def process_ack_packet(self, packet):
        """We got an ack for a message, no need to resend it."""
        ack_num = packet.msgNo
        log.info("Got ack for message %s", ack_num)
        self.packet_tracker.remove(ack_num)

    def process_reject_packet(self, packet):
        """We got a reject message for a packet.  Stop sending the message."""
        ack_num = packet.msgNo
        log.info("Got REJECT for message %s", ack_num)
        self.packet_tracker.remove(ack_num)

    def process_packet(self, packet):
        """Process a packet received from aprs-is server."""
        log.debug("ProcessPKT-LOOP %d", self._loop_cnt)
        our_call = self.callsign.lower()

        from_call = packet.from_call
        if packet.addresse:
            to_call = packet.addresse
        else:
            to_call = packet.to_call
        msg_id = packet.msgNo

        # We don't put ack or rejection packets destined for us
        # through the plugins. These are purely message control
        # packets
        if (
            isinstance(packet, packets.AckPacket)
            and packet.addresse.lower() == our_call
        ):
            self.process_ack_packet(packet)
        elif (
            isinstance(packet, packets.RejectPacket)
            and packet.addresse.lower() == our_call
        ):
            self.process_reject_packet(packet)
        else:
            # Only ack messages that were sent directly to us
            if isinstance(packet, packets.MessagePacket):
                if to_call and to_call.lower() == our_call:
                    # It's a MessagePacket and it's for us!
                    # let any threads do their thing, then ack
                    # send an ack last
                    send_via_queue(
                        packets.AckPacket(
                            from_call=self.callsign,
                            to_call=from_call,
                            msgNo=msg_id,
                        ),
                    )
                    self.process_our_message_packet(packet)
                else:
                    # Packet wasn't meant for us!
                    self.process_other_packet(packet, for_us=False)
            else:
                self.process_other_packet(
                    packet,
                    for_us=(to_call.lower() == our_call),
                )
        log.debug(f"Packet processing complete for pkt '{packet.key}'")
        return False

    def process_our_message_packet(self, packet: core.Packet):
        """Process a MessagePacket destined for us.
        Convert to an APRSMessage and call the backend_callback to send
        the message through errbot plugins
        """
        log.debug(packet)
        try:
            text = packet["message_text"]
            sender = packet["from"]
            msg_number = int(packet.get("msgNo", "0"))
            path = packet["path"]
            via = packet["via"]
        except KeyError as exc:
            log.error("malformed packet, missing key %s", exc)
            return

        msg = APRSMessage(
            body=text,
            extras={
                "msg_number": msg_number,
                "via": via,
                "path": path,
                "raw": packet["raw"],
                "packet": packet,
            },
        )
        msg.frm = APRSPerson(callsign=sender)
        msg.to = APRSPerson(self.callsign)
        self.backend_callback(msg)

    def process_other_packet(self, packet, for_us=False):
        """Process an APRS Packet that isn't a message or ack"""
        # Not implemented yet, for now just return and dump these packets
        return
