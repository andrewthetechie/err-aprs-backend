from dataclasses import dataclass
import httpx
from functools import cached_property
from aprs_backend.clients._base import ClientBase
from logging import Logger


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


class APRSRegistryClient(ClientBase):
    def __init__(
        self, registry_url: str, app_config: RegistryAppConfig, log: Logger, frequency_seconds: int = 3600
    ) -> None:
        self.registry_url = registry_url
        self.app_config = app_config
        super().__init__(log=log, frequency_seconds=frequency_seconds)

    async def __process__(self) -> None:
        """Posts to the aprs registry url for each listening callsign for the bot
        Run as an asyncio task in __call__
        """
        async with httpx.AsyncClient() as client:
            for post_json in self.app_config.post_jsons:
                self.log.debug("Posting %s to %s", post_json, self.registry_url)
                try:
                    response = await client.post(self.registry_url, json=post_json)
                    self.log.debug(response)
                    response.raise_for_status()
                except httpx.RequestError as exc:
                    self.log.error(
                        "Request Error while posting %s to %s. Error: %s",
                        post_json,
                        self.registry_url,
                        exc,
                    )
                except httpx.HTTPStatusError as exc:
                    self.log.error(
                        "Error while posting %s to %s. Error: %s, response: %s",
                        post_json,
                        self.registry_url,
                        exc,
                        response,
                    )
