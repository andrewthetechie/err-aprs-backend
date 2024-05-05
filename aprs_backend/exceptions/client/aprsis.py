from aprs_backend.exceptions.client import ClientError


class APRSISClientError(ClientError):
    pass


class APRSISConnnectError(APRSISClientError):
    pass


class APRSISLoginError(APRSISConnnectError):
    pass


class APRSISPacketError(APRSISClientError):
    pass


class APRSISDeadConnectionError(APRSISClientError):
    pass


class APRSISPacketDecodeError(APRSISClientError):
    pass
