from errbot.backends.base import Person


class APRSPerson(Person):
    """This class describes a Person on the APRS network

    Their callsign and SSID

    """

    def __init__(self, callsign: str):
        self._callsign = callsign

    @property
    def person(self) -> str:
        return self._callsign

    @property
    def client(self) -> str:
        return self._callsign

    @property
    def nick(self) -> str:
        return self._callsign

    @property
    def aclattr(self) -> str:
        return self._callsign

    @property
    def fullname(self) -> str:
        return self._callsign

    @property
    def email(self) -> None:
        return None

    @property
    def callsign(self) -> str:
        return self._callsign
