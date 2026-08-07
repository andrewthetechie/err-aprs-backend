from aprs_backend.clients import RegistryAppConfig, APRSRegistryClient
import pytest
from unittest.mock import patch, MagicMock

from logging import getLogger
import httpx


@pytest.fixture
def registry_app_config():
    return RegistryAppConfig(
        description="description", listening_callsigns=["TEST-1"], website="website", software="software"
    )


parameters = [
    ("testing", ["TEST-1"], "http://test.test", "testsoftware"),
    ("testing", ["TEST-1", "TEST-2"], "http://test.test", "testsoftware"),
    ("testing", ["TEST-1", "TEST-2", "EMLSRVR"], "https://test.test", "othersoftware"),
]


@pytest.mark.parametrize("description,listening_callsigns,website,software", parameters)
def test_RegistryAppConfig(description, listening_callsigns, website, software):
    this_RegistryAppConfig = RegistryAppConfig(
        description=description, listening_callsigns=listening_callsigns, website=website, software=software
    )

    assert len(this_RegistryAppConfig.post_jsons) == len(listening_callsigns)
    assert {post_json["callsign"] for post_json in this_RegistryAppConfig.post_jsons} == set(listening_callsigns)
    assert this_RegistryAppConfig.post_jsons[0]["description"] == description
    assert this_RegistryAppConfig.post_jsons[0]["service_website"] == website
    assert this_RegistryAppConfig.post_jsons[0]["software"] == software


@pytest.mark.asyncio
async def test_APRSRegistryClient_oneshot(httpx_mock, registry_app_config):
    httpx_mock.add_response(method="POST")

    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com", log=getLogger(__name__), app_config=registry_app_config
    )
    await this_APRSRegistryClient.__process__()


@pytest.mark.asyncio
async def test_APRSRegistryClient_errors(httpx_mock, mock_logger, registry_app_config):
    httpx_mock.add_response(method="POST", status_code=422)

    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com",
        log=mock_logger,
        app_config=registry_app_config,
    )
    await this_APRSRegistryClient.__process__()
    assert mock_logger.error.called


@pytest.mark.asyncio
async def test_APRSRegistryClient_repeats_and_errors(httpx_mock, mock_logger, registry_app_config):
    httpx_mock.add_response(method="POST")
    httpx_mock.add_exception(httpx.ReadTimeout("Unable to read within timeout"))
    httpx_mock.add_response(method="POST")

    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com", log=mock_logger, app_config=registry_app_config, frequency_seconds=1
    )
    await this_APRSRegistryClient.__process__()
    await this_APRSRegistryClient.__process__()
    await this_APRSRegistryClient.__process__()
    assert mock_logger.error.called


def test_APRSRegistryClient_timeout_seconds_default(registry_app_config):
    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com", log=getLogger(__name__), app_config=registry_app_config
    )
    assert this_APRSRegistryClient.timeout_seconds == 30.0


def test_APRSRegistryClient_timeout_seconds_custom(registry_app_config):
    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com", log=getLogger(__name__), app_config=registry_app_config, timeout_seconds=15.0
    )
    assert this_APRSRegistryClient.timeout_seconds == 15.0


@pytest.mark.asyncio
async def test_APRSRegistryClient_timeout_handled(httpx_mock, mock_logger, registry_app_config):
    httpx_mock.add_exception(httpx.ReadTimeout("Unable to read within timeout"))

    this_APRSRegistryClient = APRSRegistryClient(
        registry_url="http://test.com", log=mock_logger, app_config=registry_app_config, timeout_seconds=5.0
    )
    await this_APRSRegistryClient.__process__()
    assert mock_logger.error.called


@pytest.mark.asyncio
async def test_APRSRegistryClient_timeout_wired_into_client(registry_app_config):
    """Regression guard: prove timeout_seconds reaches httpx.AsyncClient's constructor.

    This test would fail if the timeout=httpx.Timeout(...) kwarg were removed from
    the AsyncClient call in APRSRegistryClient.__process__.
    """
    captured_kwargs = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()
            return response

    with patch("aprs_backend.clients.aprs_registry.httpx.AsyncClient", FakeAsyncClient):
        client = APRSRegistryClient(
            registry_url="http://test.com",
            log=getLogger(__name__),
            app_config=registry_app_config,
            timeout_seconds=15.0,
        )
        await client.__process__()

    assert "timeout" in captured_kwargs, "timeout kwarg was not passed to httpx.AsyncClient"
    assert isinstance(captured_kwargs["timeout"], httpx.Timeout)
    assert captured_kwargs["timeout"].connect == 15.0
    assert captured_kwargs["timeout"].read == 15.0
