import queue
import time
from copy import deepcopy
from typing import Any

from aprs_backend.clients import ErrbotAPRSISClient
from aprs_backend.clients import ErrbotKISSClient
from aprs_backend.packets.tracker import ErrbotPacketTrack
from aprs_backend.threads import ErrbotAPRSDThread
from aprs_backend.threads import send_queue
from aprs_backend.utils.log import log
from aprsd.packets import core


def send_via_queue(packet: core.Packet, block: bool = True, timeout: int = 90) -> None:
    try:
        send_queue.put(packet, block=block, timeout=timeout)
    except queue.Full:
        log.fatal(
            "Unable to send packet: %s due to send queue full and timeout %d hit",
            packet,
            timeout,
        )


def check_sender_config(config: object) -> dict[str, Any]:
    """Checks the errbot config object for the required config for an ErrbotAPRSSender"""
    sender_config = {
        "msg_rate_limit_period": int(getattr(config, "APRS_MSG_RATE_LIMIT_PERIOD", 2)),
        "ack_rate_limit_period": int(getattr(config, "APRS_ACK_RATE_LIMIT_PERIOD", 1)),
    }
    return sender_config


class ErrbotAPRSSender(ErrbotAPRSDThread):
    def __init__(
        self, client: ErrbotAPRSISClient | ErrbotKISSClient, config: dict[str, Any] = {}
    ) -> None:
        super().__init__("errbot-aprs-sender")
        self.client = client
        defaults = {
            "msg_rate_limit_period": 2,
            "ack_rate_limit_period": 1,
        }
        self.send_queue = send_queue
        defaults.update(config)
        self.config = deepcopy(defaults)
        self._loop_cnt = 1

    def loop(self):
        try:
            packet = self.send_queue.get(timeout=1)
            self.send(packet)
        except queue.Empty:
            pass
        self._loop_cnt += 1
        return True

    # TODO: figure out how to throttle like https://github.com/craigerl/aprsd/blob/master/aprsd/threads/tx.py#L40
    def send(self, packet: core.Packet, direct: bool = False) -> None:
        """Send a packet either in a thread or directly to the client."""
        # prepare the packet for sending.
        # This constructs the packet.raw
        packet.prepare()
        if isinstance(packet, core.AckPacket):
            self._send_ack(packet, direct=direct)
        else:
            self._send_packet(packet, direct=direct)

    def _send_packet(self, packet: core.Packet, direct=False):
        if not direct:
            thread = SendPacketThread(packet=packet)
            thread.start()
        else:
            self._send_direct(packet)

    def _send_ack(self, packet: core.AckPacket, direct=False):
        if not direct:
            thread = SendAckThread(packet=packet)
            thread.start()
        else:
            self._send_direct(packet)

    def _send_direct(self, packet: core.Packet) -> None:
        packet.update_timestamp()
        packet.log(header="TX")
        self.client.send(packet)


class SendAckThread(ErrbotAPRSDThread):
    loop_count: int = 1

    def __init__(self, packet: core.Packet, aprs_sender: ErrbotAPRSSender):
        self.packet = packet
        self.sender = aprs_sender
        super().__init__(f"SendAck-{self.packet.msgNo}")

    def loop(self):
        """Separate thread to send acks with retries."""
        send_now = False
        if self.packet.send_count == self.packet.retry_count:
            # we reached the send limit, don't send again
            # TODO(hemna) - Need to put this in a delayed queue?
            log.info(
                f"{self.packet.__class__.__name__}"
                f"({self.packet.msgNo}) "
                "Send Complete. Max attempts reached"
                f" {self.packet.retry_count}",
            )
            return False

        if self.packet.last_send_time:
            # Message has a last send time tracking
            now = int(round(time.time()))

            # aprs duplicate detection is 30 secs?
            # (21 only sends first, 28 skips middle)
            sleep_time = 31
            delta = now - self.packet.last_send_time
            if delta > sleep_time:
                # It's time to try to send it again
                send_now = True
            elif self.loop_count % 10 == 0:
                log.debug(f"Still wating. {delta}")
        else:
            send_now = True

        if send_now:
            self.sender.send(self.packet, direct=True)
            self.packet.send_count += 1
            self.packet.last_send_time = int(round(time.time()))

        time.sleep(1)
        self.loop_count += 1
        return True


class SendPacketThread(ErrbotAPRSDThread):
    loop_count: int = 1

    def __init__(self, packet: core.Packet, aprs_sender: ErrbotAPRSSender):
        self.packet = packet
        self.sender = aprs_sender
        self.packet = packet
        name = self.packet.raw[:5]
        super().__init__(f"TXPKT-{self.packet.msgNo}-{name}")
        pkt_tracker = ErrbotPacketTrack()
        pkt_tracker.add(packet)

    def loop(self):
        """Loop until a message is acked or it gets delayed.

        We only sleep for 5 seconds between each loop run, so
        that CTRL-C can exit the app in a short period.  Each sleep
        means the app quitting is blocked until sleep is done.
        So we keep track of the last send attempt and only send if the
        last send attempt is old enough.

        """
        pkt_tracker = ErrbotPacketTrack()
        # lets see if the message is still in the tracking queue
        packet = pkt_tracker.get(self.packet.msgNo)
        if not packet:
            # The message has been removed from the tracking queue
            # So it got acked and we are done.
            log.info(
                f"{self.packet.__class__.__name__}"
                f"({self.packet.msgNo}) "
                "Message Send Complete via Ack.",
            )
            return False
        else:
            send_now = False
            if packet.send_count == packet.retry_count:
                # we reached the send limit, don't send again
                # TODO(hemna) - Need to put this in a delayed queue?
                log.info(
                    f"{packet.__class__.__name__} "
                    f"({packet.msgNo}) "
                    "Message Send Complete. Max attempts reached"
                    f" {packet.retry_count}",
                )
                if not packet.allow_delay:
                    pkt_tracker.remove(packet.msgNo)
                return False

            # Message is still outstanding and needs to be acked.
            if packet.last_send_time:
                # Message has a last send time tracking
                now = int(round(time.time()))
                sleeptime = (packet.send_count + 1) * 31
                delta = now - packet.last_send_time
                if delta > sleeptime:
                    # It's time to try to send it again
                    send_now = True
            else:
                send_now = True

            if send_now:
                # no attempt time, so lets send it, and start
                # tracking the time.
                packet.last_send_time = int(round(time.time()))
                self.aprs_sender.send(packet, direct=True)
                packet.send_count += 1

            time.sleep(1)
            # Make sure we get called again.
            self.loop_count += 1
            return True
