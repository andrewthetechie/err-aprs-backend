import asyncio

import pytest

from aprs_backend.utils.counter import MessageCounter


@pytest.mark.asyncio
async def test_basic_increment():
    counter = MessageCounter(initial_value=1, max_message_count=999)
    val = await counter.get_value()
    assert val == 2


@pytest.mark.asyncio
async def test_basic_increment_sync():
    counter = MessageCounter(initial_value=1, max_message_count=999)
    val = counter.get_value_sync()
    assert val == 2


@pytest.mark.asyncio
async def test_overflow_wrap():
    counter = MessageCounter(initial_value=998, max_message_count=999)
    val1 = await counter.get_value()
    assert val1 == 999
    val2 = await counter.get_value()
    assert val2 == 1


@pytest.mark.asyncio
async def test_overflow_wrap_sync():
    counter = MessageCounter(initial_value=998, max_message_count=999)
    val1 = counter.get_value_sync()
    assert val1 == 999
    val2 = counter.get_value_sync()
    assert val2 == 1


@pytest.mark.asyncio
async def test_increment_false_no_bump():
    counter = MessageCounter(initial_value=5, max_message_count=999)
    val1 = await counter.get_value(increment=False)
    val2 = await counter.get_value(increment=False)
    assert val1 == 5
    assert val2 == 5


@pytest.mark.asyncio
async def test_increment_false_no_bump_sync():
    counter = MessageCounter(initial_value=5, max_message_count=999)
    val1 = counter.get_value_sync(increment=False)
    val2 = counter.get_value_sync(increment=False)
    assert val1 == 5
    assert val2 == 5


@pytest.mark.asyncio
async def test_concurrency_stress():
    """Drive many concurrent get_value() calls and assert every returned value
    is within 1.._max with no unexpected duplicates or skips beyond wrap."""
    max_val = 999
    counter = MessageCounter(initial_value=1, max_message_count=max_val)
    num_calls = 5000
    results = []

    async def call_get_value():
        v = await counter.get_value()
        results.append(v)

    await asyncio.gather(*(call_get_value() for _ in range(num_calls)))

    # Every value must be within range
    for v in results:
        assert 1 <= v <= max_val, f"Value {v} out of range 1-{max_val}"

    # With num_calls increments starting from initial_value=1, the counter
    # cycles through 1..max_val repeatedly. Collect the sequence in order of
    # expected values: the first call returns 2, second returns 3, ...,
    # wrapping back. We check that the sorted results match the expected
    # distribution of values across the cycles.
    expected_count = num_calls // max_val
    remainder = num_calls % max_val
    for v in range(1, max_val + 1):
        count = results.count(v)
        # Each value appears expected_count times, plus one extra for the
        # first `remainder` values in the wrap sequence.
        expected = expected_count
        # Values 2 through (remainder+1) get an extra hit (since initial=1,
        # first increment yields 2).
        if 2 <= v <= remainder + 1:
            expected += 1
        assert count == expected, f"Value {v} appeared {count} times, expected {expected}"
