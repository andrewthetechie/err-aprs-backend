import threading
from datetime import datetime

import wrapt
from aprs_backend.packets.seen import ErrbotPacketsSeenList
from aprsd.packets.packet_list import PacketList


class ErrbotPacketList(PacketList):
    """Singleton class that tracks packets"""

    _instance = None
    lock = threading.Lock()
    _total_rx: int = 0
    _total_tx: int = 0
    _last_packet_rx: datetime = None
    _last_packet_tx: datetime = None
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
        self._last_packet_rx = datetime.now()
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
        self._last_packet_tx = datetime.now()
        ErrbotPacketsSeenList().update_seen(packet)

    @wrapt.synchronized(lock)
    def get_last_rx(self):
        return self._last_packet_rx

    @wrapt.synchronized(lock)
    def get_last_tx(self):
        return self._last_packet_tx

    @property
    def secs_since_last_rx(self) -> float:
        now = datetime.now()
        if self.get_last_rx() is not None:
            return (now - self.get_last_rx()).total_seconds()
        return 0.0


    @property
    def secs_since_last_tx(self) -> float:
        now = datetime.now()
        return (now - self.get_last_tx()).total_seconds()
