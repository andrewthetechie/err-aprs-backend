from aprs_backend.exceptions import APRSBackendException


class ClientError(APRSBackendException):
    pass


class ConnectError(ClientError):
    pass
