"""Wire-format compatibility tests for the ``address`` / ``addresse`` field rename.

PRD #454 renamed the Python field from ``addresse`` to ``address`` across the
Packet class hierarchy.  These tests pin the serialized JSON shape so that
future changes cannot silently break the wire-format contract.

The ``.json`` property is referenced in-repo only as a debug-log argument
(aprs_backend/aprs.py, aprs_backend/clients/beacon.py).  No RPC server
implementation exists in this repository.  ``from_dict`` is called only on the
aprslib parse path in parser.py, where the legacy ``addresse`` key is already
hand-translated to ``address``.

The compatibility shim ensures:
- Outbound JSON always emits ``addresse`` (legacy wire key).
- Inbound JSON/dict accepts both ``addresse`` and ``address``.
"""

import json

import pytest

from aprs_backend.packets import AckPacket, MessagePacket, Packet, RejectPacket


@pytest.mark.parametrize(
    "packet_cls,factory_kwargs",
    [
        (Packet, {"from_call": "W1AW", "to_call": "W2AW", "address": "TEST"}),
        (
            AckPacket,
            {"from_call": "W1AW", "to_call": "W2AW", "address": "TEST", "msgNo": "001"},
        ),
        (
            RejectPacket,
            {"from_call": "W1AW", "to_call": "W2AW", "address": "TEST", "msgNo": "001"},
        ),
        (
            MessagePacket,
            {
                "from_call": "W1AW",
                "to_call": "W2AW",
                "address": "TEST",
                "msgNo": "001",
                "message_text": "hello",
            },
        ),
    ],
)
def test_to_json_emits_legacy_addresse_key(packet_cls, factory_kwargs):
    """Outbound to_json() must emit ``addresse`` (not ``address``)."""
    packet = packet_cls(**factory_kwargs)
    data = json.loads(packet.to_json())
    assert "addresse" in data, f"Expected 'addresse' key in {packet_cls.__name__} JSON"
    assert data["addresse"] == "TEST"
    assert "address" not in data, f"'address' key must not appear in {packet_cls.__name__} JSON"


@pytest.mark.parametrize(
    "packet_cls,factory_kwargs",
    [
        (Packet, {"from_call": "W1AW", "to_call": "W2AW", "address": "TEST"}),
        (
            AckPacket,
            {"from_call": "W1AW", "to_call": "W2AW", "address": "TEST", "msgNo": "001"},
        ),
        (
            RejectPacket,
            {"from_call": "W1AW", "to_call": "W2AW", "address": "TEST", "msgNo": "001"},
        ),
        (
            MessagePacket,
            {
                "from_call": "W1AW",
                "to_call": "W2AW",
                "address": "TEST",
                "msgNo": "001",
                "message_text": "hello",
            },
        ),
    ],
)
def test_json_property_emits_legacy_addresse_key(packet_cls, factory_kwargs):
    """The .json property (used by debug logging) must emit ``addresse``."""
    packet = packet_cls(**factory_kwargs)
    data = json.loads(packet.json)
    assert "addresse" in data
    assert data["addresse"] == "TEST"


@pytest.mark.parametrize(
    "packet_cls,legacy_json",
    [
        (Packet, '{"addresse": "LEGACY", "from_call": "W1AW"}'),
        (
            AckPacket,
            '{"addresse": "LEGACY", "from_call": "W1AW", "msgNo": "001"}',
        ),
        (
            RejectPacket,
            '{"addresse": "LEGACY", "from_call": "W1AW", "msgNo": "001"}',
        ),
        (
            MessagePacket,
            '{"addresse": "LEGACY", "from_call": "W1AW", "msgNo": "001", "message_text": "hi"}',
        ),
    ],
)
def test_from_json_accepts_legacy_addresse_key(packet_cls, legacy_json):
    """Inbound from_json() must accept the legacy ``addresse`` key."""
    packet = packet_cls.from_json(legacy_json)
    assert packet.address == "LEGACY"


@pytest.mark.parametrize(
    "packet_cls,current_json",
    [
        (Packet, '{"address": "CURRENT", "from_call": "W1AW"}'),
        (
            AckPacket,
            '{"address": "CURRENT", "from_call": "W1AW", "msgNo": "001"}',
        ),
        (
            RejectPacket,
            '{"address": "CURRENT", "from_call": "W1AW", "msgNo": "001"}',
        ),
        (
            MessagePacket,
            '{"address": "CURRENT", "from_call": "W1AW", "msgNo": "001", "message_text": "hi"}',
        ),
    ],
)
def test_from_json_accepts_current_address_key(packet_cls, current_json):
    """Inbound from_json() must also accept the current ``address`` key."""
    packet = packet_cls.from_json(current_json)
    assert packet.address == "CURRENT"


@pytest.mark.parametrize(
    "packet_cls,legacy_dict",
    [
        (Packet, {"addresse": "LEGACY", "from_call": "W1AW"}),
        (AckPacket, {"addresse": "LEGACY", "from_call": "W1AW", "msgNo": "001"}),
        (RejectPacket, {"addresse": "LEGACY", "from_call": "W1AW", "msgNo": "001"}),
        (
            MessagePacket,
            {"addresse": "LEGACY", "from_call": "W1AW", "msgNo": "001", "message_text": "hi"},
        ),
    ],
)
def test_from_dict_accepts_legacy_addresse_key(packet_cls, legacy_dict):
    """Inbound from_dict() must accept the legacy ``addresse`` key."""
    packet = packet_cls.from_dict(legacy_dict)
    assert packet.address == "LEGACY"


@pytest.mark.parametrize(
    "packet_cls,current_dict",
    [
        (Packet, {"address": "CURRENT", "from_call": "W1AW"}),
        (AckPacket, {"address": "CURRENT", "from_call": "W1AW", "msgNo": "001"}),
        (RejectPacket, {"address": "CURRENT", "from_call": "W1AW", "msgNo": "001"}),
        (
            MessagePacket,
            {"address": "CURRENT", "from_call": "W1AW", "msgNo": "001", "message_text": "hi"},
        ),
    ],
)
def test_from_dict_accepts_current_address_key(packet_cls, current_dict):
    """Inbound from_dict() must also accept the current ``address`` key."""
    packet = packet_cls.from_dict(current_dict)
    assert packet.address == "CURRENT"


@pytest.mark.parametrize(
    "packet_cls,factory_kwargs",
    [
        (Packet, {"from_call": "W1AW", "to_call": "W2AW", "address": "W2AW"}),
        (
            AckPacket,
            {"from_call": "W1AW", "to_call": "W2AW", "address": "W2AW", "msgNo": "001"},
        ),
        (
            RejectPacket,
            {"from_call": "W1AW", "to_call": "W2AW", "address": "W2AW", "msgNo": "001"},
        ),
        (
            MessagePacket,
            {
                "from_call": "W1AW",
                "to_call": "W2AW",
                "address": "W2AW",
                "msgNo": "001",
                "message_text": "hello",
            },
        ),
    ],
)
def test_roundtrip_preserves_address(packet_cls, factory_kwargs):
    """Serializing then deserializing must preserve the address field."""
    original = packet_cls(**factory_kwargs)
    serialized = original.to_json()
    restored = packet_cls.from_json(serialized)
    assert restored.address == original.address
    assert restored.from_call == original.from_call
