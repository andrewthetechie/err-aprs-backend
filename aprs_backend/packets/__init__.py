from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
from aprs_backend.utils.counter import MessageCounter
from aprs_backend.utils.position import latitude_to_ddm, longitude_to_ddm
from aprs_backend.utils.datetime import init_timestamp
from datetime import datetime, timezone
from better_profanity import profanity
from aprs_backend.version import __version__ as BACKEND_VERSION


@dataclass_json
@dataclass(unsafe_hash=True)
class Packet:
    _type: str = field(default="Packet", hash=False)
    from_call: str | None = field(default=None)
    to_call: str | None = field(default=None)
    addresse: str | None = field(default=None)
    format: str | None = field(default=None)
    msgNo: str | None = field(default=None)  # noqa: N815
    packet_type: str | None = field(default=None)
    timestamp: float = field(default_factory=init_timestamp, compare=False, hash=False)
    # Holds the raw text string to be sent over the wire
    # or holds the raw string from input packet
    raw: str | None = field(default=None, compare=False, hash=False)
    raw_dict: dict = field(repr=False, default_factory=lambda: {}, compare=False, hash=False)
    # Built by calling prepare().  raw needs this built first.
    payload: str | None = field(default=None)

    # Fields related to sending packets out
    last_send_time: float = field(repr=False, default=0, compare=False, hash=False)
    last_send_attempt: int = field(repr=False, default=0, compare=False, hash=False)

    path: list[str] = field(default_factory=list, compare=False, hash=False)
    via: str | None = field(default=None, compare=False, hash=False)

    @property
    def to(self):
        return self.addresse if self.addresse is not None else self.to_call

    @property
    def json(self):
        """get the json formated string.

        This is used soley by the rpc server to return json over the wire.
        """
        return self.to_json()

    def get(self, key: str, default: str | None = None):
        """Emulate a getter on a dict."""
        if hasattr(self, key):
            return getattr(self, key)
        else:
            return default

    @property
    def key(self) -> str:
        """Build a key for finding this packet in a dict."""
        return f"{self.from_call}:{self.addresse}:{self.msgNo}"

    def update_timestamp(self) -> None:
        self.timestamp = init_timestamp()

    @property
    def human_info(self) -> str:
        """Build a human readable string for this packet.

        This doesn't include the from to and type, but just
        the human readable payload.
        """
        self.prepare()
        msg = self._filter_for_send(self.raw).rstrip("\n")
        return msg

    async def prepare(self, message_counter: MessageCounter) -> None:
        """Do stuff here that is needed prior to sending over the air."""
        # now build the raw message for sending
        if not self.msgNo:
            self.msgNo = await message_counter.get_value()
        self._build_payload()
        self._build_raw()

    def _build_payload(self) -> None:
        """The payload is the non headers portion of the packet."""
        if not self.to_call:
            raise ValueError("to_call isn't set. Must set to_call before calling prepare()")

        # The base packet class has no real payload
        self.payload = f":{self.to_call.ljust(9)}"

    def _build_raw(self) -> None:
        """Build the self.raw which is what is sent over the air."""
        self.raw = "{}>APERRB:{}".format(
            self.from_call,
            self.payload,
        )

    def _filter_for_send(self, msg: str | None) -> str:
        """Limit message size based on best guess fo displayability"""
        # max?  ftm400 displays 64, raw msg shows 74
        # and ftm400-send is max 64.  setting this to
        # 67 displays 64 on the ftm400. (+3 {01 suffix)
        return msg[:67] if msg else ""

    def __str__(self) -> str:
        """Show the raw version of the packet"""
        self._build_payload()
        self._build_raw()
        if not self.raw:
            raise ValueError("self.raw is unset")
        return self.raw

    def __repr__(self) -> str:
        """Build the repr version of the packet."""
        repr = f"{self.__class__.__name__}:" f" From: {self.from_call}  " f"   To: {self.to_call}"
        return repr


@dataclass_json
@dataclass(unsafe_hash=True)
class AckPacket(Packet):
    _type: str = field(default="AckPacket", hash=False)

    def _build_payload(self):
        self.payload = f":{self.to_call: <9}:ack{self.msgNo}"


@dataclass_json
@dataclass(unsafe_hash=True)
class RejectPacket(Packet):
    _type: str = field(default="RejectPacket", hash=False)
    response: str | None = field(default=None)

    def _build_payload(self):
        self.payload = f":{self.to_call: <9}:rej{self.msgNo}"


@dataclass_json
@dataclass(unsafe_hash=True)
class MessagePacket(Packet):
    _type: str = field(default="MessagePacket", hash=False)
    message_text: str | None = field(default=None)

    def _build_payload(self):
        self.payload = ":{}:{}{{{}".format(
            self.to_call.ljust(9),
            self._filter_for_send(self.message_text).rstrip("\n"),
            str(self.msgNo),
        )


@dataclass_json
@dataclass(unsafe_hash=True)
class PositionPacket(Packet):
    _type: str = field(default="GPSPacket", hash=False)
    latitude: float = field(default=0.00)
    longitude: float = field(default=0.00)
    altitude: float = field(default=0.00)
    rng: float = field(default=0.00)
    posambiguity: int = field(default=0)
    messagecapable: bool = field(default=False)
    comment: str | None = field(default=None)
    symbol: str = field(default="l")
    symbol_table: str = field(default="/")
    raw_timestamp: str | None = field(default=None)
    object_name: str | None = field(default=None)
    object_format: str | None = field(default=None)
    alive: bool | None = field(default=None)
    course: int | None = field(default=None)
    speed: float | None = field(default=None)
    phg: str | None = field(default=None)
    phg_power: int | None = field(default=None)
    phg_height: float | None = field(default=None)
    phg_gain: int | None = field(default=None)
    phg_dir: str | None = field(default=None)
    phg_range: float | None = field(default=None)
    phg_rate: int | None = field(default=None)
    # http://www.aprs.org/datum.txt
    daodatumbyte: str | None = field(default=None)

    def _build_time_zulu(self) -> datetime:
        """Build the timestamp in UTC/zulu."""
        if self.timestamp:
            return datetime.fromtimestamp(self.timestamp, timezone.utc).strftime("%d%H%M")

    def _build_payload(self) -> None:
        """The payload is the non headers portion of the packet."""
        time_zulu = self._build_time_zulu()
        lat = latitude_to_ddm(self.latitude)
        long = longitude_to_ddm(self.longitude)
        payload = ["@" if self.timestamp else "!", time_zulu, lat, self.symbol_table, long, self.symbol]

        if self.altitude:
            payload.append(self.formatted_altitude)

        if self.comment:
            # run a profanity filter, just in case.
            payload.append(profanity.censor(self.comment))

        self.payload = "".join(payload)

    def _build_raw(self) -> None:
        self.raw = f"{self.from_call}>{self.to_call},WIDE2-1:{self.payload}"

    @property
    def formatted_altitude(self):
        altitude = self.altitude / 0.3048  # to feet
        altitude = min(999999, altitude)
        altitude = max(-99999, altitude)
        return f"/A={altitude:06.0f}"

    @property
    def human_info(self) -> str:
        h_str = []
        h_str.append(f"Lat:{self.latitude:03.3f}")
        h_str.append(f"Lon:{self.longitude:03.3f}")
        if self.altitude:
            h_str.append(f"Altitude:{self.altitude:03.0f}")
        if self.speed:
            h_str.append(f"Speed:{self.speed:03.0f}MPH")
        if self.course:
            h_str.append(f"Course:{self.course:03.0f}")
        if self.rng:
            h_str.append(f"RNG:{self.rng:03.0f}")
        if self.phg:
            h_str.append(f"PHG:{self.phg}")

        return " ".join(h_str)


@dataclass_json
@dataclass(unsafe_hash=True)
class BeaconPacket(PositionPacket):
    _type: str = field(default="BeaconPacket", hash=False)

    def _build_payload(self) -> None:
        """The payload is the non headers portion of the packet."""
        time_zulu = self._build_time_zulu()
        lat = latitude_to_ddm(self.latitude)
        lon = longitude_to_ddm(self.longitude)

        self.payload = f"@{time_zulu}z{lat}{self.symbol_table}{lon}"

        if self.comment:
            comment = self._filter_for_send(self.comment)
            self.payload = f"{self.payload}{self.symbol}{comment}"
        else:
            self.payload = f"{self.payload}{self.symbol}ErrAprsBackend Beacon {BACKEND_VERSION}"

    def _build_raw(self) -> None:
        self.raw = f"{self.from_call}>APERRB:" f"{self.payload}"
