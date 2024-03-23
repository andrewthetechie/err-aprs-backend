import time

from aprsd.client import APRSISClient
from aprsd.clients.aprsis import Aprsdis
from aprslib.exceptions import LoginError

import logging


log = logging.getLogger(__name__)

class ErrbotAPRSISClient(APRSISClient):
    callsign: str = None
    password: int = None
    aprs_host: str = "rotate.aprs2.netZ"
    aprs_port: int = 14580

    @staticmethod
    def is_configured():
        return True

    def _check_config(
        self,
        callsign: str | None = None,
        password: int | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> bool:
        """
        Sets config on the object to any non-none passed in arguments and then checks that
        there is the required config to connect. Returns true if object has required config.
        """
        # setup object's config
        if callsign is not None:
            self.callsign = callsign
        if password is not None:
            self.password = password
        if host is not None:
            self.host = host
        if port is not None:
            self.port = port

        # check for required config
        for attr in ["callsign", "password", "aprs_host", "aprs_port"]:
            if getattr(self, attr, None) is None:
                log.error("Unable to connect client, missing %s", attr)
                return False
        return True

    def setup_connection(
        self,
        callsign: str | None = None,
        password: int | None = None,
        host: str | None = None,
        port: int | None = None,
    ):
        connected = False
        backoff = 1
        aprs_client = None

        if not self._check_config(
            callsign=callsign, password=password, host=host, port=port
        ):
            return

        while not connected:
            try:
                log.info("Creating aprslib client")
                aprs_client = Aprsdis(
                    self.callsign,
                    passwd=str(self.password),
                    host=self.host,
                    port=self.port,
                )
                # Force the log to be the same
                aprs_client.logger = log
                aprs_client.connect()
                connected = True
                backoff = 1
            except LoginError as exc:
                log.error("Failed to login to APRS-IS Server '%s'", exc)
                connected = False
                time.sleep(backoff)
            except Exception as exc:
                log.error("Unable to connect to APRS-IS server. '%s' ", exc)
                connected = False
                time.sleep(backoff)
                # Don't allow the backoff to go to inifinity.
                if backoff > 5:
                    backoff = 5
                else:
                    backoff += 1
                continue
        log.debug("Logging in to APRS-IS with user '%s'", callsign)
        self._client = aprs_client
        return aprs_client
