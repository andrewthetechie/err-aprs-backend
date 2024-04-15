from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
import time
import re
from aprs_backend.utils.counter import MessageCounter


def _init_timestamp():
    """Build a unix style timestamp integer"""
    return int(round(time.time()))

@dataclass_json
@dataclass(unsafe_hash=True)
class Packet:
    _type: str = field(default="Packet", hash=False)
    from_call: str | None = field(default=None)
    to_call: str | None = field(default=None)
    addresse: str | None = field(default=None)
    format: str | None = field(default=None)
    msgNo: str | None = field(default=None)   # noqa: N815
    packet_type: str | None = field(default=None)
    timestamp: float = field(default_factory=_init_timestamp, compare=False, hash=False)
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
        self.timestamp = _init_timestamp()

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
        self.payload = (
            f":{self.to_call.ljust(9)}"
        )

    def _build_raw(self) -> None:
        """Build the self.raw which is what is sent over the air."""
        self.raw = "{}>APZ100:{}".format(
            self.from_call,
            self.payload,
        )

    def _filter_for_send(self, msg) -> str:
        """Filter and format message string for FCC."""
        # max?  ftm400 displays 64, raw msg shows 74
        # and ftm400-send is max 64.  setting this to
        # 67 displays 64 on the ftm400. (+3 {01 suffix)
        # feature req: break long ones into two msgs
        if not msg:
            return ""

        message = msg[:67]
        # We all miss George Carlin
        return re.sub(
            "fuck|shit|cunt|piss|cock|bitch", "****",
            message, flags=re.IGNORECASE,
        )

    def __str__(self) -> str:
        """Show the raw version of the packet"""
        self._build_payload()
        self._build_raw()
        if not self.raw:
            raise ValueError("self.raw is unset")
        return self.raw

    def __repr__(self) -> str:
        """Build the repr version of the packet."""
        repr = (
            f"{self.__class__.__name__}:"
            f" From: {self.from_call}  "
            f"   To: {self.to_call}"
        )
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
