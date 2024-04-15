from errbot.backends.base import Message
from aprs_backend.packets import MessagePacket
from aprs_backend.person import APRSPerson

class APRSMessage(Message):
    @property
    def is_direct(self):
        return True

    @classmethod
    def from_message_packet(cls, packet: MessagePacket) -> "APRSMessage":
        this_msg = cls(
            body=packet.message_text,
            extras={
                "msgNo": packet.msgNo,
                "via": packet.via,
                "path": packet.path,
                "raw": packet.raw,
                "packet": packet,
            }
        )
        this_msg.frm = APRSPerson(callsign=packet.from_call)
        this_msg.to = APRSPerson(callsign=packet.addresse)
        return this_msg
