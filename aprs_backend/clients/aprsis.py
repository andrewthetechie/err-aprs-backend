import logging
import asyncio
from functools import cached_property
import time
from aprs_backend.exceptions import (
    APRSISClientError,
    APRSISConnnectError,
    APRSISLoginError,
    APRSISPacketError,
    APRSISDeadConnectionError,
    APRSISPacketDecodeError,
)


class APRSISClient:
    def __init__(
        self,
        callsign: str,
        password: int,
        host: str = "rotate.aprs2.net",
        port: int = 14580,
        aprs_filter: str = "DEFAULT",
        aprs_app_name: str = "ErrbotAPRS",
        app_version: str = "",
        logger: logging.Logger | None = None,
        keepalive_seconds: int = 120,
    ):
        self.callsign = callsign
        self.password = password
        self.aprs_host = host
        self.aprs_port = port
        self.aprs_filter = aprs_filter
        self._aprs_app_name = aprs_app_name
        self._app_version = app_version
        self._keepalive_seconds = keepalive_seconds

        self._log = logger if logger is not None else logging.getLogger(__name__)

        self.connected = False
        self.__connect_count = 0
        self.__packet_count = 0
        self._writer = None
        self._reader = None
        self._keepalive_last_sent = 0
        self._last_successful_connect = 0

    @cached_property
    def _aprs_login(self) -> bytes:
        base_str = f"user {self.callsign} pass {self.password} vers {self._aprs_app_name} {self._app_version}"
        if self.aprs_filter.lower() != "default":
            base_str = base_str + f" filter {self.aprs_filter}\r\n"
        return base_str

    async def _send_login(self):
        """
        Sends login string to server
        """

        self._log.info("Sending login information")
        try:
            await self._send(self._aprs_login)
            aprs_version = await self._reader.readline()
            aprs_version = aprs_version.decode("latin-1").rstrip()
            aprs_login_test = await self._reader.readline()
            aprs_login_test = aprs_login_test.decode("latin-1").rstrip()
            self._log.debug("APRS server version Response %s", aprs_version)
            _, _, callsign, status, _, server = aprs_login_test.split(" ", 5)
            status = status.replace(",", "").lower()

            if callsign == "":
                raise APRSISLoginError("Server responded with empty callsign???")
            if callsign != self.callsign:
                raise APRSISLoginError("Server responsed with: %s" % aprs_login_test)
            if status != "verified" and self.password != "-1":  # nosec not a hardcoded password
                raise APRSISLoginError("Password is incorrect")

            if self.password == "-1":  # nosec not a hardcoded password
                self._log.info("Login successful (receive only)")
            else:
                self._log.info("Login successful")
        except APRSISLoginError as e:
            self._log.error(str(e))
            await self.disconnect()
            raise
        except Exception as exc:
            await self.disconnect()
            self._log.error("Failed to login %s", str(exc))
            raise APRSISLoginError("Failed to login") from exc

    @cached_property
    def _keepalive_packet(self) -> bytes:
        return b"#keepalive\n"

    async def connect(self) -> None:
        self.__connect_count += 1
        try:
            self._reader, self._writer = await asyncio.open_connection(self.aprs_host, self.aprs_port)
            # login to aprsis
            await self._send_login()
            self._last_successful_connect = time.perf_counter()
            self._log.info(
                "Connected to %s/%s:%s as %s with filter %s",
                self.aprs_host,
                self._get_sock_peer_ip(self._writer),
                self.aprs_port,
                self.callsign,
                self.aprs_filter,
            )
            self.connected = True
        except Exception as exc:
            self._log.error("Error while connecting: %s", exc)
            self.connected = False
            raise APRSISConnnectError from exc

    async def disconnect(self):
        self._log.info("Disconnecting from aprsis")
        self._writer.close()
        await self._writer.wait_closed()
        self._writer = None
        self._reader = None
        self.connected = False
        self._log.info("Disconnected")

    async def _send(self, packet: str, encoding: str = "utf-8") -> bool:
        self._log.debug("Sending '%s'", packet)
        packet = packet.rstrip("\r\n") + "\r\n"
        if packet is None:
            self._log.error("Packet is None - %s - Dropping", packet)
            return False
        if self._writer is not None:
            self._writer.write(packet.encode(encoding))
            await self._writer.drain()
            return True
        else:
            # disconnected, not able to send packet yet
            return False

    async def _send_keepalive(self) -> bool:
        """
        Send KeepAlive packet if necessary. _writer must be connected.
        :return Whether or not one was sent.
        """
        now = time.perf_counter()
        if self.connected:
            if (now - self._keepalive_last_sent) > self._keepalive_seconds:
                self._log.debug(f"Sending keepalive to {self._get_sock_peer_ip(self._writer)}")
                await self._send(self._keepalive_packet)
                self._keepalive_last_sent = now
                return True
        return False

    async def get_packet(self) -> str:
        """Get a packet from APRSIS

        Raises:
            APRSISPacketError: _description_
            APRSISDeadConnectionError: _description_

        Returns:
            str | None: _description_
        """
        if not self.connected:
            raise APRSISConnnectError("Not connected")
        try:
            # Read packet string from socket
            packet_bytes = await self._reader.readline()
        except Exception as exc:
            logging.error("Could not read packet: %s", exc)
            raise APRSISPacketError from exc

        if not packet_bytes:
            # zero length packets can be returned if keepalives have failed after ~30m
            self._log.warning("Empty packet received. Probably missed keepalives.")
            raise APRSISDeadConnectionError("Empty packet received. Probably missed keepalives")

        try:
            return_packet = packet_bytes.decode()
        except UnicodeDecodeError as decode_err:
            raise APRSISPacketDecodeError from decode_err
        except Exception as exc:
            raise APRSISClientError from exc
        self.__packet_count += 1
        self._log.debug("Received %d total packets", self.__packet_count)
        return return_packet

    @staticmethod
    def _get_sock_peer_ip(writer):
        sock = writer.get_extra_info("socket")
        if sock:
            return sock.getpeername()[0]
        return None
