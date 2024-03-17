from aprslib.exceptions import LoginError
from aprsd.client import APRSISClient
from aprsd.clients.aprsis import Aprsdis
import time

from aprs_backend.utils.log import log


class ErrbotAPRSISClient(APRSISClient):

    @staticmethod
    def is_configured():
        return True

    def setup_connection(self, callsign: str, password: int, host: str = "rotate.aprs2.net", port: int = 14580):
        connected = False
        backoff = 1
        aprs_client = None
        while not connected:
            try:
                log.info("Creating aprslib client")
                aprs_client = Aprsdis(callsign, passwd=str(password), host=host, port=port)
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