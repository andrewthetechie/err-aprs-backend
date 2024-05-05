from aprs_backend.clients._base import ClientBase
from dataclasses import dataclass
import asyncio
from functools import cached_property
from aprs_backend.packets import BeaconPacket
from logging import Logger
from datetime import datetime


@dataclass
class BeaconConfig:
    from_call: str
    latitude: float
    longitude: float
    symbol: str = "l"
    symbol_table: str = "/"
    comment: str | None = None

    @cached_property
    def beacon_packet(self) -> BeaconPacket:
        packet = BeaconPacket(
            from_call=self.from_call,
            latitude=self.latitude,
            longitude=self.longitude,
            symbol=self.symbol,
            symbol_table=self.symbol_table,
            comment=self.comment,
        )
        packet._build_raw()
        return packet


class BeaconClient(ClientBase):
    def __init__(
        self, beacon_config: BeaconConfig, send_queue: asyncio.Queue, log: Logger, frequency_seconds: int = 3600
    ) -> None:
        self.config: BeaconConfig = beacon_config
        self.send_queue = send_queue
        self.last_sent = None
        super().__init__(log=log, frequency_seconds=frequency_seconds)

    async def __process__(self):
        try:
            self.send_queue.put_nowait(self.config.beacon_packet)
            self.last_sent = datetime.now()
            self.log.debug("Beacon Packet %s put in send queue", self.config.beacon_packet.json)
        except asyncio.QueueFull:
            self.log.error("Send queue is full, can't send beacon packet %s", self.config.beacon_packet.json)
