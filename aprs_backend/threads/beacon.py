import time

from aprs_backend.threads import ErrbotAPRSDThread
from aprs_backend.threads.tx import send_via_queue
from aprsd.packets import core

import logging


log = logging.getLogger(__name__)

def check_beacon_config(config: object) -> dict:
    kwargs = {
        "beacon_comment": getattr(
            config, "APRS_BEACON_COMMENT", "Beacon from Errbot-APRS Backend"
        ),
        "beacon_interval_minutes": int(
            getattr(config, "APRS_BEACON_FREQUENCY_MINUTES", "90")
        ),
        "beacon_symbol": getattr(config, "APRS_BEACON_SYMBOL", "/"),
    }
    for key in ["latitude", "longitude"]:
        config_key = f"APRS_BEACON_{key}".upper()
        if (value := getattr(config, config_key, None)) is None:
            raise ValueError(
                f"{config_key} not found in config and required for Beacon."
            )
        kwargs[key] = value
    return kwargs


class BeaconSendThread(ErrbotAPRSDThread):
    """Thread that sends a GPS beacon packet periodically."""

    _loop_cnt: float = 1

    def __init__(
        self,
        latitude: str,
        longitude: str,
        callsign: str,
        beacon_comment: str = "",
        beacon_interval_minutes: int = 90,
        beacon_symbol: str = "/",
    ):
        super().__init__("BeaconSendThread")
        self._loop_cnt = 1
        self.latitude = latitude
        self.longitude = longitude
        self.callsign = callsign
        self.beacon_comment = beacon_comment
        self.beacon_interval_minutes = beacon_interval_minutes
        self.beacon_symbol = beacon_symbol
        log.info(
            "Beacon thread is running and will send " "beacons every %d minutes.",
            self.beacon_interval_minutes,
        )

    def loop(self):
        # Only beacon interval seconds, but sleep the minium possible so that CTRL-C can stll work to kill the errbot
        if self._loop_cnt % self.beacon_interval == 0:
            log.debug("Sending beacon at loop count %f", self._loop_cnt)
            pkt = core.BeaconPacket(
                from_call=self.callsign,
                to_call="APRS",
                latitude=float(self.latitude),
                longitude=float(self.longitude),
                comment=self.beacon_comment,
                symbol=self.beacon_symbol,
            )
            send_via_queue(pkt)
        self._loop_cnt += 0.25
        time.sleep(0.25)
        return True
