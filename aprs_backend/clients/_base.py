import asyncio
from logging import Logger


class ClientBase:
    def __init__(self, log: Logger, frequency_seconds: int = 3600, chunk_seconds: int = 10):
        self.log = log
        self.frequency_seconds = frequency_seconds
        self.chunk_seconds = chunk_seconds

    async def __process__(self):
        raise NotImplementedError("Not implemented")  # pragma: no cover

    def _handle_cancelled(self) -> None:
        """Centralized cancellation handler for ClientBase.

        Swallows CancelledError via return (does not re-raise).
        This is intentional: the production caller (aprs_backend/aprs.py)
        cancels registry_client/beacon_client tasks and does not await them
        afterward; they are not part of any asyncio.gather/TaskGroup/asyncio.timeout,
        so no parent coroutine relies on CancelledError propagation here.
        """
        self.log.info("%s cancelled, stopping", self.__class__.__name__)

    async def __call__(self) -> None:
        """Posts to the aprs registry url for each listening callsign for the bot
        Run as an asyncio task
        """
        self.log.debug("Staring %s", self.__class__.__name__)
        try:
            while True:
                await self.__process__()
                # sleep in chunks for cancellability
                chunk_seconds = min(self.chunk_seconds, self.frequency_seconds)
                remaining = self.frequency_seconds
                while remaining > 0:
                    sleep_time = min(chunk_seconds, remaining)
                    try:
                        await asyncio.sleep(sleep_time)
                    except asyncio.CancelledError:
                        self._handle_cancelled()
                        return
                    remaining -= sleep_time
        except asyncio.CancelledError:
            self._handle_cancelled()
            return
