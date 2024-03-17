import time
from queue import Queue

import aprslib
from aprs_backend.clients import ErrbotAPRSISClient
from aprs_backend.clients import ErrbotKISSClient
from aprs_backend.packets.list import ErrbotPacketList
from aprs_backend.threads import ErrbotAPRSDThread
from aprs_backend.utils.log import log
from aprsd import packets


class ErrbotRXThread(ErrbotAPRSDThread):
    def __init__(self, packet_queue: Queue, client: ErrbotAPRSISClient | ErrbotKISSClient):
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
                self.process_packet, raw=False, blocking=False,
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
        print(packet)
        if isinstance(packet, packets.AckPacket):
            # We don't need to drop AckPackets, those should be
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
                log.warning(f"Packet {packet.from_call}:{packet.msgNo} already tracked, dropping.")
            else:
                log.warning(
                    f"Packet {packet.from_call}:{packet.msgNo} already tracked "
                    f"but older than {30} seconds. processing.",
                )
                self._packet_list.rx(packet)
                self.packet_queue.put(packet)
