from dataclasses import dataclass
import httpx
from functools import cached_property
import asyncio


@dataclass
class RegistryAppConfig:
    description: str
    listening_callsigns: list[str]
    website: str = ""
    software: str = ""

    @cached_property
    def post_jsons(self) -> list[dict]:
        return [
            {
                "callsign": str(this_call),
                "description": self.description,
                "service_website": self.website,
                "software": self.software,
            }
            for this_call in self.listening_callsigns
        ]


class APRSRegistryClient:
    def __init__(self, registry_url: str, app_config: RegistryAppConfig, log, frequency_seconds: int = 3600) -> None:
        self.registry_url = registry_url
        self.log = log
        self.frequency_seconds = frequency_seconds
        self.app_config = app_config

    async def __call__(self) -> None:
        """Posts to the aprs registry url for each listening callsign for the bot
        Run as an asyncio task
        """
        self.log.debug("Staring APRS Registry Client")
        try:
            while True:
                async with httpx.AsyncClient() as client:
                    for post_json in self.app_config.post_jsons:
                        self.log.debug("Posting %s to %s", post_json, self.registry_url)
                        try:
                            response = await client.post(self.registry_url, json=post_json)
                            self.log.debug(response)
                            response.raise_for_status()
                        except httpx.RequestError as exc:
                            self.log.error(
                                "Request Error while posting %s to %s. Error: %s, response: %s",
                                post_json,
                                self.registry_url,
                                exc,
                                response,
                            )
                        except httpx.HTTPStatusError as exc:
                            self.log.error(
                                "Error while posting %s to %s. Error: %s, response: %s",
                                post_json,
                                self.registry_url,
                                exc,
                                response,
                            )
                # instead of sleeping in one big chunk, sleep in smaller chunks for easier cacnellation
                for i in range(self.frequency_seconds * 10):
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self.log.info("APRS client cancelled, stopping")
            return
