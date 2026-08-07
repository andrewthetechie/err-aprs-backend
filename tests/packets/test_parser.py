from aprs_backend.packets.parser import hash_packet
import pytest


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
