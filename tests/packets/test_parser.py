import asyncio
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aprs_backend.packets import MessagePacket
from aprs_backend.packets.parser import hash_packet


def test_hash_is_deterministic():
    """Same (to, addresse, msg_no) always produces the same hash."""
    h1 = hash_packet("W1AW", "W2AW", "001")
    h2 = hash_packet("W1AW", "W2AW", "001")
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest length


def test_hash_normalizes_station_order():
    """Swapped to/addresse arguments produce the same hash (alphabetically sorted)."""
    h1 = hash_packet("W2AW", "W1AW", "001")
    h2 = hash_packet("W1AW", "W2AW", "001")
    assert h1 == h2


def test_hash_uses_lru_cache():
    """Identical inputs hit the lru_cache on a second call."""
    hash_packet.cache_clear()
    hash_packet("W1AW", "W2AW", "001")
    info_before = hash_packet.cache_info()
    hash_packet("W1AW", "W2AW", "001")
    info_after = hash_packet.cache_info()
    assert info_after.hits == info_before.hits + 1


def test_different_inputs_produce_different_hashes():
    """Different msg_no produces a different hash."""
    h1 = hash_packet("W1AW", "W2AW", "001")
    h2 = hash_packet("W1AW", "W2AW", "002")
    assert h1 != h2


def test_hash_handles_none_to():
    """None for 'to' is normalized to empty string (no TypeError)."""
    h = hash_packet(None, "W2AW", "001")
    assert isinstance(h, str)
    assert len(h) == 64


def test_hash_handles_none_addresse():
    """None for 'addresse' is normalized to empty string (no TypeError)."""
    h = hash_packet("W1AW", None, "001")
    assert isinstance(h, str)
    assert len(h) == 64


def test_hash_handles_none_msg_no():
    """None for 'msg_no' is normalized to empty string (no TypeError)."""
    h = hash_packet("W1AW", "W2AW", None)
    assert isinstance(h, str)
    assert len(h) == 64


def test_hash_handles_all_none():
    """All-None inputs produce a defined hash instead of a degenerate '-None'."""
    h = hash_packet(None, None, None)
    assert isinstance(h, str)
    assert len(h) == 64
    # The pre-image is ",".join(("", "")) + "-" + "" = ",-"
    expected = hashlib.sha256(b",-").hexdigest()
    assert h == expected


def test_hash_none_inputs_are_distinct_from_non_none():
    """A None field produces a different hash than the same call with a value."""
    h_none = hash_packet(None, "W2AW", "001")
    h_value = hash_packet("W1AW", "W2AW", "001")
    assert h_none != h_value


@pytest.mark.asyncio
async def test_process_message_dedup_skips_repeated_packet():
    """The dedup path in _process_message skips a repeated packet (same to/addresse/msgNo)."""
    from aprs_backend.aprs import APRSBackend

    # Build two MessagePackets with identical (to, addresse, msgNo)
    packet1 = MessagePacket(
        from_call="W1AW",
        to_call="W2AW",
        addresse="W2AW",
        msgNo="001",
        message_text="hello",
    )
    packet2 = MessagePacket(
        from_call="W1AW",
        to_call="W2AW",
        addresse="W2AW",
        msgNo="001",
        message_text="hello again",
    )
    # A third packet with a different msgNo should NOT be deduplicated
    packet3 = MessagePacket(
        from_call="W1AW",
        to_call="W2AW",
        addresse="W2AW",
        msgNo="002",
        message_text="different message",
    )

    # Verify both packets produce the same hash
    h1 = hash_packet(packet1.to, packet1.addresse, packet1.msgNo)
    h2 = hash_packet(packet2.to, packet2.addresse, packet2.msgNo)
    assert h1 == h2

    # Mock the APRSBackend minimally to exercise _process_message
    with patch.object(APRSBackend, "__init__", lambda self, config: None):
        backend = APRSBackend(None)
        backend._packet_cache = {}
        backend._packet_cache_lock = asyncio.Lock()
        backend._ack_message = AsyncMock()
        backend.callback_message = MagicMock()

        # First packet should NOT be deduped — callback_message called
        await backend._process_message(packet1)
        assert backend.callback_message.call_count == 1

        # Second identical packet SHOULD be deduped — callback_message NOT called again
        await backend._process_message(packet2)
        assert backend.callback_message.call_count == 1

        # Third distinct packet should NOT be deduped
        await backend._process_message(packet3)
        assert backend.callback_message.call_count == 2
