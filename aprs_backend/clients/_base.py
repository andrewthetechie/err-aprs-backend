import asyncio
from logging import Logger


class ClientBase:
    def __init__(self, log: Logger, frequency_seconds: int = 3600):
        self.log = log
        self.frequency_seconds = frequency_seconds

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
                # instead of sleeping in one big chunk, sleep in smaller chunks for easier cacnellation
                for i in range(self.frequency_seconds * 10):
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self.log.info("%scancelled, stopping", self.__class__.__name__)
            return
