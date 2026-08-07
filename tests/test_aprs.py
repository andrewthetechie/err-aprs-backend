import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aprs_backend.aprs import APRSBackend
from aprs_backend.packets import MessagePacket


class InstrumentedLock:
    """Wrapper around asyncio.Lock that counts acquisitions."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self.acquire_count = 0

    async def __aenter__(self):
        self.acquire_count += 1
        await self._lock.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self._lock.__aexit__(*args)


class _BotConfig:
    """Minimal bot config for constructing APRSBackend."""

    BOT_IDENTITY = {"callsign": "TEST-1", "password": "1234"}
    APRS_BOT_CALLSIGN = "TEST-1"
    APRS_CONNECT_TIMEOUT = "30.0"
    APRS_SEND_MAX_QUEUE = "2048"
    APRS_MAX_DROPPED_PACKETS = "25"
    APRS_MAX_CACHED_PACETS = "2048"
    APRS_MESSAGE_MAX_RETRIES = "7"
    APRS_MESSAGE_RETRY_WAIT = "90"
    APRS_STRIP_NEWLINES = "true"
    APRS_LANGUAGE_FILTER = "false"
    APRS_MAX_AGE_CACHED_PACETS_SECONDS = "3600"
    APRS_REGISTRY_ENABLED = "false"
    APRS_BEACON_ENABLE = "false"
    # ErrBot base class requirements
    BOT_PREFIX = "!"
    BOT_ASYNC = False
    BOT_ALT_PREFIXES = ()
    BOT_ALT_PREFIX_CASEINSENSITIVE = False
    MESSAGE_SIZE_LIMIT = None


@pytest.fixture
def bot_config():
    return _BotConfig()


@pytest.fixture
def backend(bot_config):
    """Create an APRSBackend instance with mocked _client."""
    with patch("aprs_backend.aprs.APRSISClient"):
        backend = APRSBackend(bot_config)
    backend._client = AsyncMock()
    # Mock send_message to avoid needing a live plugin_manager
    backend.send_message = MagicMock()
    return backend


def _make_packet(msgno: int = 1, last_send_attempt: int = 0, last_send_time: datetime | None = None):
    """Helper to create a MessagePacket for _waiting_ack."""
    pkt = MessagePacket(
        from_call="TEST-1",
        to_call="REMOTE-1",
        addresse="REMOTE-1",
        message_text="hello",
        msgNo=str(msgno),
        last_send_attempt=last_send_attempt,
    )
    pkt.last_send_time = last_send_time or datetime.now()
    return pkt


def _run_one_cycle(backend):
    """Run retry_worker() for exactly one cycle by patching the trailing sleep(5)
    to set an event and then sleep forever.  The caller waits for the event,
    cancels the task, and swallows CancelledError."""
    event = asyncio.Event()

    original_sleep = asyncio.sleep

    async def patched_sleep(delay):
        if delay == 5:
            # End of one cycle — signal and block so the worker stays
            # paused here until the caller cancels it.
            event.set()
            await original_sleep(999999)
        else:
            await original_sleep(delay)

    return event, patched_sleep


# ---------------------------------------------------------------------------
# Test: retry_worker acquires lock O(1) per cycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_worker_single_lock_acquisition_per_cycle(backend):
    """retry_worker must acquire _waiting_ack_lock only once per cycle
    when snapshotting entries (O(1) not O(N))."""

    instrumented = InstrumentedLock()
    backend._waiting_ack_lock = instrumented

    pkt = _make_packet(msgno=1, last_send_attempt=1, last_send_time=datetime.now() - timedelta(seconds=200))
    backend._waiting_ack["REMOTE-1-1"] = pkt

    event, patched_sleep = _run_one_cycle(backend)

    with patch("aprs_backend.aprs.asyncio.sleep", patched_sleep):
        task = asyncio.create_task(backend.retry_worker())
        await event.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert instrumented.acquire_count == 1


# ---------------------------------------------------------------------------
# Test: concurrent ACK/REJ processing — no RuntimeError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_worker_no_runtime_error_under_concurrent_drop(backend):
    """Concurrent __drop_message_from_waiting while retry_worker iterates
    must not raise RuntimeError: dictionary changed size during iteration."""

    # Seed _waiting_ack with several entries
    for i in range(1, 6):
        pkt = _make_packet(msgno=i, last_send_attempt=1, last_send_time=datetime.now() - timedelta(seconds=200))
        backend._waiting_ack[f"REMOTE-1-{i}"] = pkt

    runtime_error_raised = False

    async def concurrent_drops():
        nonlocal runtime_error_raised
        try:
            for i in range(1, 6):
                await asyncio.sleep(0.001)
                await backend._APRSBackend__drop_message_from_waiting(f"REMOTE-1-{i}")
        except RuntimeError as exc:
            if "dictionary changed size during iteration" in str(exc):
                runtime_error_raised = True
            raise

    event, patched_sleep = _run_one_cycle(backend)

    with patch("aprs_backend.aprs.asyncio.sleep", patched_sleep):
        retry_task = asyncio.create_task(backend.retry_worker())
        drop_task = asyncio.create_task(concurrent_drops())
        await event.wait()
        retry_task.cancel()
        try:
            await retry_task
        except asyncio.CancelledError:
            pass
        await drop_task

    assert not runtime_error_raised


# ---------------------------------------------------------------------------
# Test: no entry processed more than once during concurrent iteration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_worker_no_duplicate_processing(backend):
    """Each entry in the snapshot must be processed at most once per cycle."""

    processed_keys = []

    original_drop = backend._APRSBackend__drop_message_from_waiting

    async def tracked_drop(message_hash: str) -> None:
        processed_keys.append(message_hash)
        await original_drop(message_hash)

    backend._APRSBackend__drop_message_from_waiting = tracked_drop

    # Seed entries that exceed max retries so they get dropped
    for i in range(1, 6):
        pkt = _make_packet(msgno=i, last_send_attempt=8, last_send_time=datetime.now() - timedelta(seconds=200))
        backend._waiting_ack[f"REMOTE-1-{i}"] = pkt

    event, patched_sleep = _run_one_cycle(backend)

    with patch("aprs_backend.aprs.asyncio.sleep", patched_sleep):
        task = asyncio.create_task(backend.retry_worker())
        await event.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Each key should appear at most once
    assert len(processed_keys) == len(set(processed_keys))


# ---------------------------------------------------------------------------
# Test: max-retry drop path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_worker_drops_entry_over_max_retries(backend):
    """An entry whose last_send_attempt > _message_max_retry is dropped
    via __drop_message_from_waiting and removed from _waiting_ack."""

    pkt = _make_packet(msgno=1, last_send_attempt=8, last_send_time=datetime.now())
    backend._waiting_ack["REMOTE-1-1"] = pkt

    # Patch __drop_message_from_waiting to track calls
    drop_called_with = []

    async def tracked_drop(message_hash: str) -> None:
        drop_called_with.append(message_hash)
        async with backend._waiting_ack_lock:
            backend._waiting_ack.pop(message_hash, None)

    backend._APRSBackend__drop_message_from_waiting = tracked_drop

    event, patched_sleep = _run_one_cycle(backend)

    with patch("aprs_backend.aprs.asyncio.sleep", patched_sleep):
        task = asyncio.create_task(backend.retry_worker())
        await event.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert "REMOTE-1-1" in drop_called_with
    assert "REMOTE-1-1" not in backend._waiting_ack


# ---------------------------------------------------------------------------
# Test: resend-timing path — overdue triggers send, recent does not
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_worker_resends_overdue_but_not_recent(backend):
    """An entry whose elapsed time since last_send_time exceeds
    _message_retry_wait triggers send_message, while a recently-sent
    entry does not."""

    # Overdue packet (sent 200 seconds ago, wait is 90s)
    overdue_pkt = _make_packet(msgno=1, last_send_attempt=1, last_send_time=datetime.now() - timedelta(seconds=200))
    backend._waiting_ack["REMOTE-1-1"] = overdue_pkt

    # Recent packet (sent 10 seconds ago, wait is 90s)
    recent_pkt = _make_packet(msgno=2, last_send_attempt=1, last_send_time=datetime.now() - timedelta(seconds=10))
    backend._waiting_ack["REMOTE-1-2"] = recent_pkt

    sent_messages = []

    def track_send(msg):
        sent_messages.append(msg)

    backend.send_message = MagicMock(side_effect=track_send)

    event, patched_sleep = _run_one_cycle(backend)

    with patch("aprs_backend.aprs.asyncio.sleep", patched_sleep):
        task = asyncio.create_task(backend.retry_worker())
        await event.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Only the overdue packet should trigger a send
    assert len(sent_messages) == 1
    # The recent packet should NOT have triggered a send
    # (it's still in _waiting_ack since it wasn't over max retries)
    assert "REMOTE-1-2" in backend._waiting_ack


# ---------------------------------------------------------------------------
# Test: max-retries check ordering — checked before resend-timing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_worker_checks_max_retries_before_timing(backend):
    """Max-retries check must be evaluated before resend-timing check.
    An entry over max retries should be dropped even if it is also overdue."""

    # Entry that is both over max retries AND overdue
    pkt = _make_packet(msgno=1, last_send_attempt=8, last_send_time=datetime.now() - timedelta(seconds=200))
    backend._waiting_ack["REMOTE-1-1"] = pkt

    drop_called = False
    send_called = False

    async def tracked_drop(message_hash: str) -> None:
        nonlocal drop_called
        drop_called = True
        async with backend._waiting_ack_lock:
            backend._waiting_ack.pop(message_hash, None)

    backend._APRSBackend__drop_message_from_waiting = tracked_drop

    def track_send(msg):
        nonlocal send_called
        send_called = True

    backend.send_message = MagicMock(side_effect=track_send)

    event, patched_sleep = _run_one_cycle(backend)

    with patch("aprs_backend.aprs.asyncio.sleep", patched_sleep):
        task = asyncio.create_task(backend.retry_worker())
        await event.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert drop_called, "Entry over max retries should be dropped"
    assert not send_called, "Entry over max retries should NOT be resent (max-retries check first)"
    assert "REMOTE-1-1" not in backend._waiting_ack
