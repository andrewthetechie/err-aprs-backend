import time
from queue import Queue

import aprslib
from aprs_backend.clients import ErrbotAPRSISClient
from aprs_backend.clients import ErrbotKISSClient
from aprs_backend.packets.list import ErrbotPacketList
from aprs_backend.threads import ErrbotAPRSDThread
from aprsd import packets
from aprs_backend.packets.ackrej import parse_ack_rej_msg_id, parse_new_ackrej_format
import logging


log = logging.getLogger(__name__)

class ErrbotRXThread(ErrbotAPRSDThread):
    def __init__(
        self, packet_queue: Queue, client: ErrbotAPRSISClient | ErrbotKISSClient
    ):
        super().__init__("RX_MSG")
        self.packet_queue = packet_queue
        self._client = client
        self._packet_list = ErrbotPacketList()

    def stop(self):
        self.thread_stop = True
        self._client.client.stop()

    def loop(self):
        # setup the consumer of messages and block until a messages
        try:
            # This will register a packet consumer with aprslib
            # When new packets come in the consumer will process
            # the packet

            # Do a partial here because the consumer signature doesn't allow
            # For kwargs to be passed in to the consumer func we declare
            # and the aprslib developer didn't want to allow a PR to add
            # kwargs.  :(
            # https://github.com/rossengeorgiev/aprs-python/pull/56
            self._client.client.consumer(
                self.process_packet,
                raw=False,
                blocking=False,
            )

        except (
            aprslib.exceptions.ConnectionDrop,
            aprslib.exceptions.ConnectionError,
        ):
            log.error("Connection dropped, reconnecting")
            time.sleep(5)
            # Force the deletion of the client object connected to aprs
            # This will cause a reconnect, next time client.get_client()
            # is called
            self._client.reset()
        # Continue to loop
        return True

    def process_packet(self, *args, **kwargs):
        """This handles the processing of an inbound packet.

        When a packet is received by the connected client object,
        it sends the raw packet into this function.  This function then
        decodes the packet via the client, and then processes the packet.
        Ack Packets are sent to the packet_queue for processing.
        All other packets have to be checked as a dupe, and then only after
        we haven't seen this packet before, do we send it to the
        packet_queue for processing.
        """
        packet = self._client.decode_packet(*args, **kwargs)
        packet.log(header="RX")
        log.debug(packet)

        # Check if this packet is in the new ack-rej format
        # arpslib cannot handle these messages properly so we have to apply a workaround
        # as we don't resubmit data in case it hasn't been received
        response = None
        if isinstance(packet, packets.MessagePacket):
            if packet.message_text is not None and packet.message_text != "":
                packet.message_text, response = parse_ack_rej_msg_id(packet.message_text)


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
        is_new_ackrej = False
        if packet.msgNo is None and packet.message_text is not None:
            packet.message_text, packet.msgNo, is_new_ackrej = parse_new_ackrej_format(packet.message_text)

        log.debug("Message %s is_new_ackrej %s", packet, is_new_ackrej)

        if response == "ack":
            log.debug("Packet is new style ack, transforming")
            new_packet = packets.AckPacket(
                from_call = packet.from_call,
                to_call = packet.to_call,
                addresse = packet.addresse,
                format = packet.format,
                msgNo = packet.msgNo,
                packet_type = packet.packet_type,
                timestamp = packet.timestamp,
                raw = packet.raw,
                raw_dict = packet.raw_dict,
                payload = packet.payload,
                send_count = packet.send_count,
                retry_count = packet.retry_count,
                last_send_time = packet.last_send_time,
                last_send_attempt = packet.last_send_attempt,
                allow_delay = packet.allow_delay,
                path = packet.path,
                via = packet.va,
                response = response
            )
            packet = new_packet
        if response == "rej":
            log.debug("Packet is new style rejection, transforming")
            new_packet = packets.RejectPacket(
                from_call = packet.from_call,
                to_call = packet.to_call,
                addresse = packet.addresse,
                format = packet.format,
                msgNo = packet.msgNo,
                packet_type = packet.packet_type,
                timestamp = packet.timestamp,
                raw = packet.raw,
                raw_dict = packet.raw_dict,
                payload = packet.payload,
                send_count = packet.send_count,
                retry_count = packet.retry_count,
                last_send_time = packet.last_send_time,
                last_send_attempt = packet.last_send_attempt,
                allow_delay = packet.allow_delay,
                path = packet.path,
                via = packet.va,
                response = response
            )
            packet = new_packet

        if isinstance(packet, packets.AckPacket) or isinstance(packet, packets.RejectPacket):
            # We don't need to drop AckPackets of Rejects, those should be
            # processed.
            self.packet_queue.put(packet)
        else:
            # Make sure we aren't re-processing the same packet
            # For RF based APRS Clients we can get duplicate packets
            # So we need to track them and not process the dupes.
            found = False
            try:
                # Find the packet in the list of already seen packets
                # Based on the packet.key
                found = self._packet_list.find(packet)
            except KeyError:
                found = False

            if not found:
                # If we are in the process of already ack'ing
                # a packet, we should drop the packet
                # because it's a dupe within the time that
                # we send the 3 acks for the packet.
                self._packet_list.rx(packet)
                self.packet_queue.put(packet)
            elif packet.timestamp - found.timestamp < 30:
                # If the packet came in within 60 seconds of the
                # Last time seeing the packet, then we drop it as a dupe.
                log.warning(
                    f"Packet {packet.from_call}:{packet.msgNo} already tracked, dropping."
                )
            else:
                log.warning(
                    f"Packet {packet.from_call}:{packet.msgNo} already tracked "
                    f"but older than {30} seconds. processing.",
                )
                self._packet_list.rx(packet)
                self.packet_queue.put(packet)
