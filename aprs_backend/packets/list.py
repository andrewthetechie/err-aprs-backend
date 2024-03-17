import threading
from aprsd.packets.packet_list import PacketList
from aprs_backend.packets.seen import ErrbotPacketsSeenList
import wrapt


class ErrbotPacketList(PacketList):
    """Singleton class that tracks packets"""
    _instance = None
    lock = threading.Lock()
    _total_rx: int = 0
    _total_tx: int = 0
    types = {}

    @wrapt.synchronized(lock)
    def rx(self, packet):
        """Add a packet that was received."""
        self._total_rx += 1
        self._add(packet)
        ptype = packet.__class__.__name__
        if ptype not in self.types:
            self.types[ptype] = {"tx": 0, "rx": 0}
        self.types[ptype]["rx"] += 1
        ErrbotPacketsSeenList().update_seen(packet)

    @wrapt.synchronized(lock)
    def tx(self, packet):
        """Add a packet that was received."""
        self._total_tx += 1
        self._add(packet)
        ptype = packet.__class__.__name__
        if ptype not in self.types:
            self.types[ptype] = {"tx": 0, "rx": 0}
        self.types[ptype]["tx"] += 1
        ErrbotPacketsSeenList().update_seen(packet)