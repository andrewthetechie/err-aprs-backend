import asyncio
from logging import Logger


class ClientBase:
    def __init__(self, log: Logger, frequency_seconds: int = 3600, chunk_seconds: int = 10):
        self.log = log
        self.frequency_seconds = frequency_seconds
        self.chunk_seconds = chunk_seconds

    async def __process__(self):
        raise NotImplementedError("Not implemented")  # pragma: no cover

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
                        self.log.info("%s cancelled, stopping", self.__class__.__name__)
                        return
                    remaining -= sleep_time
        except asyncio.CancelledError:
            self.log.info("%scancelled, stopping", self.__class__.__name__)
            return
