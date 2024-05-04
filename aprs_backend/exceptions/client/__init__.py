from aprs_backend.exceptions.base import APRSBackendException


class ClientError(APRSBackendException):
    pass


class ConnectError(ClientError):
    pass
