import asyncio
from dataclasses import dataclass
import httpx
from functools import cached_property
from aprs_backend.clients._base import ClientBase
from logging import Logger


@dataclass
class RegistryAppConfig:
    description: str
    listening_callsigns: set[str]
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
        self,
        registry_url: str,
        app_config: RegistryAppConfig,
        log: Logger,
        frequency_seconds: int = 3600,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.registry_url = registry_url
        self.app_config = app_config
        self.timeout_seconds = timeout_seconds
        super().__init__(log=log, frequency_seconds=frequency_seconds)

    async def __process__(self) -> None:
        """Posts to the aprs registry url for each listening callsign for the bot
        Run as an asyncio task in __call__
        """
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            results = await asyncio.gather(
                *(self._post_and_log(client, post_json) for post_json in self.app_config.post_jsons),
                return_exceptions=True,
            )
            for post_json, result in zip(self.app_config.post_jsons, results):
                if isinstance(result, Exception):
                    if isinstance(result, httpx.HTTPStatusError):
                        self.log.error(
                            "Registry POST failed for %s: %s, response: %s",
                            post_json,
                            result,
                            result.response,
                        )
                    else:
                        self.log.error(
                            "Registry POST failed for %s: %s",
                            post_json,
                            result,
                        )

    async def _post_and_log(self, client: httpx.AsyncClient, post_json: dict) -> None:
        """Send a single POST to the registry, log debug info, and raise on HTTP errors."""
        self.log.debug("Posting %s to %s", post_json, self.registry_url)
        response = await client.post(self.registry_url, json=post_json)
        self.log.debug(response)
        response.raise_for_status()
