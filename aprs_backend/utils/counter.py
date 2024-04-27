import asyncio
from threading import RLock


class MessageCounter:
    def __init__(self, initial_value: int = 1, max_message_count: int = 999):
        self._lock = asyncio.Lock()
        self._sync_lock = RLock()
        self._value = initial_value
        self._max = max_message_count

    async def increment(self):
        async with self._lock:
            self._value += 1
            if self._value > self._max:
                self._value = 1

    async def get_value(self, increment: bool = True) -> int:
        if increment:
            await self.increment()
        async with self._lock:
            this_val = self._value
        return this_val

    def get_value_sync(self, increment: bool = True) -> int:
        if increment:
            with self._sync_lock:
                self._value += 1
            if self._value > self._max:
                self._value = 1
        with self._sync_lock:
            this_val = self._value
        return this_val
