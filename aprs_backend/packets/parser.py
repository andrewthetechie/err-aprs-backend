import aprslib
from aprs_backend.exceptions.packets.parser import PacketParseError
import re
import logging
from functools import lru_cache
from hashlib import sha256
from aprs_backend.packets import AckPacket, RejectPacket, MessagePacket

log = logging.getLogger(__name__)


def parse(packet_str: str) -> AckPacket | RejectPacket | MessagePacket | None:
    try:
        raw_aprs_packet = aprslib.parse(packet_str)
    except aprslib.exceptions.ParseError as exc:
        raise PacketParseError from exc
    except aprslib.exceptions.UnknownFormat as exc:
        raise PacketParseError from exc

    # Extract base data from the APRS packet

    # Text of the message
    message_text: str | None = raw_aprs_packet.get("message_text")

    # response could indicate if this packet is a potential ack or a rej
    response: str | None = raw_aprs_packet.get("response")
    if response is not None:
        response = response.lower()

    # msgNo, the message number if present in the incoming message
    # this is optional in the APRS spec
    msg_no: str | None = raw_aprs_packet.get("msgNo")

    # By default, assume that we deal with the old ack/rej format
    is_new_ackrej: bool = False

    # Callsign of the user that sent this message
    from_callsign: str | None = raw_aprs_packet.get("from")
    if from_callsign:
        from_callsign = from_callsign.upper()

    # Get the format of the message
    # For a message the bot needs to process, this value has to be 'message'
    # and not 'response'.
    # APRSlib does return ack/rej messages as format type "message".
    # however, the message text is empty for such cases

    # Check if the message is in the new ack-rej format using regex
    # Update response and message_text if we have a new ack/rej message
    if raw_aprs_packet.get("format") == "message" and message_text is not None:
        matches = re.search(r"^(ack|rej)(..)}(..)$", message_text, re.IGNORECASE)
        if matches:
            response = matches[1]
            message_text = None

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
    # the user for all messages that relate to the original one.
    # aprslib does currently not recognise these new message IDs
    # If we don't have a msg_no already and do have message_text, this might
    # be a new ack/rej
    if msg_no is None and message_text is not None:
        message_text, msg_no, is_new_ackrej = check_for_new_ackrej_format(message_text=message_text)

    raw_aprs_packet["from"] = from_callsign
    raw_aprs_packet["message_text"] = message_text
    raw_aprs_packet["msgNo"] = msg_no
    raw_aprs_packet["is_new_ackrej"] = is_new_ackrej
    raw_aprs_packet["packet_type"] = get_packet_type(raw_aprs_packet)

    match raw_aprs_packet["packet_type"]:
        case "MESSAGE":
            packet = MessagePacket.from_dict(raw_aprs_packet)
            packet.from_call = from_callsign

        case "ACK":
            packet = AckPacket.from_dict(raw_aprs_packet)
            packet.from_call = from_callsign

        case "REJECT":
            packet = RejectPacket.from_dict(raw_aprs_packet)
            packet.from_call = from_callsign

        case _:
            log.info("Packet is not a message, ack, or reject. Not parsing it")
            packet = None

    return packet


def check_for_new_ackrej_format(message_text: str) -> tuple[str, str, bool]:
    """
    Have a look at the incoming APRS message and check if it
    contains a message no which does not follow the APRS
    standard (see aprs101.pdf chapter 14)

    http://www.aprs.org/aprs11/replyacks.txt

    but rather follow the new format

    http://www.aprs.org/aprs11/replyacks.txt

    Parameters
    ==========
    message_text: 'str'
        The original aprs message as originally extracted by aprslib

    Returns
    =======
    msg: 'str'
        original message OR the modified message minus message no and trailing
        data
    msg_no: 'str'
        Null if no message_no was present
    new_ackrej_format: 'bool'
        True if the ackrej_format has to follow the new ack-rej handling
        process as described in http://www.aprs.org/aprs11/replyacks.txt
    """

    """
    The following assumptions apply when handling APRS messages in general:

    Option 1: no message ID present:
        send no ACK
        outgoing messages have no msg number attachment

            Example data exchange 1:
            DF1JSL-4>APRS,TCPIP*,qAC,T2PRT::WXBOT    :94043
            WXBOT>APRS,qAS,KI6WJP::DF1JSL-4 :Mountain View CA. Today,Sunny High 60

            Example data exchange 2:
            DF1JSL-4>APRS,TCPIP*,qAC,T2SPAIN::EMAIL-2  :jsl24469@gmail.com Hallo
            EMAIL-2>APJIE4,TCPIP*,qAC,AE5PL-JF::DF1JSL-4 :Email sent to jsl24469@gmail.com


    Option 2: old message number format is present: (example: msg{12345)
        Send ack with message number from original message (ack12345)
        All outgoing messages have trailing msg number ( {abcde ); can be numeric or
        slphanumeric counter. See aprs101.pdf chapter 14

            Example data exchange 1:
            DF1JSL-4>APRS,TCPIP*,qAC,T2SP::EMAIL-2  :jsl24469@gmail.com Hallo{12345
            EMAIL-2>APJIE4,TCPIP*,qAC,AE5PL-JF::DF1JSL-4 :ack12345
            EMAIL-2>APJIE4,TCPIP*,qAC,AE5PL-JF::DF1JSL-4 :Email sent to jsl24469@gmail.com{891
            DF1JSL-4>APOSB,TCPIP*,qAS,DF1JSL::EMAIL-2  :ack891

            Example data exchange 2:
            DF1JSL-4>APRS,TCPIP*,qAC,T2CSNGRAD::EMAIL-2  :jsl24469@gmail.com{ABCDE
            EMAIL-2>APJIE4,TCPIP*,qAC,AE5PL-JF::DF1JSL-4 :ackABCDE
            EMAIL-2>APJIE4,TCPIP*,qAC,AE5PL-JF::DF1JSL-4 :Email sent to jsl24469@gmail.com{893
            DF1JSL-4>APOSB,TCPIP*,qAS,DF1JSL::EMAIL-2  :ack893


    Option 3: new messages with message ID but without trailing retry msg ids: msg{AB}
        Do NOT send extra ack
        All outgoing messages have 2-character msg id, followed by message ID from original message
        Example:
        User sends message "Hello{AB}" to MPAD
        MPAD responds "Message content line 1{DE}AB" to user
        MPAD responds "Message content line 2{DF}AB" to user

        AB -> original message
        DE, DF -> message IDs generated by MPAD

            Example data exchange 1:
            DF1JSL-4>APRS,TCPIP*,qAC,T2NUERNBG::WXBOT    :99801{AB}
            WXBOT>APRS,qAS,KI6WJP::DF1JSL-4 :Lemon Creek AK. Today,Scattered Rain/Snow and Patchy Fog 50% High 4{QL}AB
            DF1JSL-4>APOSB,TCPIP*,qAS,DF1JSL::WXBOT    :ackQL}AB
            WXBOT>APRS,qAS,KI6WJP::DF1JSL-4 :0{QM}AB
            DF1JSL-4>APOSB,TCPIP*,qAS,DF1JSL::WXBOT    :ackQM}AB

            Example data exchange 2:
            DF1JSL-4>APRS,TCPIP*,qAC,T2SPAIN::EMAIL-2  :jsl24469@gmail.com Hallo{AB}
            EMAIL-2>APJIE4,TCPIP*,qAC,AE5PL-JF::DF1JSL-4 :Email sent to jsl24469@gmail.com{OQ}AB
            DF1JSL-4>APOSB,TCPIP*,qAS,DF1JSL::EMAIL-2  :ackOQ}AB


    Option 4: new messages with message ID and with trailing retry msg ids: msg{AB}CD
        We don't handle retries - therefore, apply option #3 for processing these
        the "CD" part gets omitted and is not used

            Example data exchange 1:
            DF1JSL-4>APRS,TCPIP*,qAC,T2CZECH::WXBOT    :99801{LM}AA
            WXBOT>APRS,qAS,KI6WJP::DF1JSL-4 :Lemon Creek AK. Today,Scattered Rain/Snow and Patchy Fog 50% High 4{QP}LM
            DF1JSL-4>APOSB,TCPIP*,qAS,DF1JSL::WXBOT    :ackQP}LM
            WXBOT>APRS,qAS,KI6WJP::DF1JSL-4 :0{QQ}LM
            DF1JSL-4>APOSB,TCPIP*,qAS,DF1JSL::WXBOT    :ackQQ}LM

            Example data exchange 2:
            DF1JSL-4>APRS,TCPIP*,qAC,T2SP::EMAIL-2  :jsl24469@gmail.com Welt{DE}FG
            EMAIL-2>APJIE4,TCPIP*,qAC,AE5PL-JF::DF1JSL-4 :Email sent to jsl24469@gmail.com{OS}DE
            DF1JSL-4>APOSB,TCPIP*,qAS,DF1JSL::EMAIL-2  :ackOS}DE

    """
    msg = msgno = None
    new_ackrej_format = False

    # if message text is present, split up between aaaaaa{bb}cc
    # where aaaaaa = message text
    # bb = message number
    # cc = message retry (may or may not be present)
    if message_text:
        matches = re.search(r"^(.*){([a-zA-Z0-9]{2})}(\w*)$", message_text, re.IGNORECASE)
        if matches:
            try:
                msg = matches[1].rstrip()
                msgno = matches[2]
                new_ackrej_format = True
            except Exception:
                msg = message_text
                msgno = None
                new_ackrej_format = False
        else:
            msg = message_text
    else:
        msg = message_text
    return msg, msgno, new_ackrej_format


def get_packet_type(packet: dict) -> str:
    """Decode the packet type from the packet."""

    packet_format = packet.get("format", "none")
    msg_response = packet.get("response", "none")
    packet_type = "UNKNOWN"
    match packet_format.lower():
        case "message":
            match msg_response:
                case "ack":
                    packet_type = "ACK"
                case "rej":
                    packet_type = "REJECT"
                case _:
                    packet_type = "MESSAGE"
        case "mic-e":
            packet_type = "MIC-E"
        case _:
            packet_type = "UNKNOWN"
    return packet_type


@lru_cache(maxsize=128)
def hash_packet(packet: AckPacket | MessagePacket | RejectPacket) -> str:
    return sha256(f"{packet.to}-{packet.msgNo}-{packet.from_call}".encode()).hexdigest()
