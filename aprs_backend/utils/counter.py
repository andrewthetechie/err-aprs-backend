import asyncio
from threading import Lock


class MessageCounter:
    def __init__(self, initial_value: int = 1, max_message_count: int = 999):
        self._lock = Lock()
        self._value = initial_value
        self._max = max_message_count

    async def increment(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._increment)

    async def get_value(self, increment: bool = True) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_value, increment)

    def get_value_sync(self, increment: bool = True) -> int:
        return self._get_value(increment)

    def _increment(self) -> None:
        with self._lock:
            self._value += 1
            if self._value > self._max:
                self._value = 1

    def _get_value(self, increment: bool = True) -> int:
        with self._lock:
            if increment:
                self._value += 1
                if self._value > self._max:
                    self._value = 1
            return self._value
