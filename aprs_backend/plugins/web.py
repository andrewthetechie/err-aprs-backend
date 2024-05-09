import logging
from threading import Thread

from webtest import TestApp
from werkzeug.serving import ThreadedWSGIServer

from errbot import BotPlugin, webhook
from errbot.core_plugins import flask_app


class APRSWebserver(BotPlugin):
    def __init__(self, *args, **kwargs):
        self.server = None
        self.server_thread = None
        self.ssl_context = None
        self.test_app = TestApp(flask_app)
        # TODO: Make this configurable in the APRS bot config, since there's no plugin config anymore
        self.web_config = {"HOST": "0.0.0.0", "PORT": 3141}  # nosec
        super().__init__(*args, **kwargs)

    def activate(self):
        if self.server_thread and self.server_thread.is_alive():
            raise Exception("Invalid state, you should not have a webserver already running.")
        self.server_thread = Thread(target=self.run_server, name="Webserver Thread")
        self.server_thread.start()
        self.log.debug("Webserver started.")

        super().activate()

    def deactivate(self):
        if self.server is not None:
            self.log.info("Shutting down the internal webserver.")
            self.server.shutdown()
            self.log.info("Waiting for the webserver thread to quit.")
            self.server_thread.join()
            self.log.info("Webserver shut down correctly.")
        super().deactivate()

    def run_server(self):
        host = self.web_config["HOST"]
        port = self.web_config["PORT"]
        self.log.info("Starting the webserver on %s:%i", host, port)
        try:
            self.server = ThreadedWSGIServer(
                host,
                port,
                flask_app,
            )
            wsgi_log = logging.getLogger("werkzeug")
            wsgi_log.setLevel(self.bot_config.BOT_LOG_LEVEL)
            self.server.serve_forever()
        except KeyboardInterrupt:
            self.log.info("Keyboard interrupt, request a global shutdown.")
            self.server.shutdown()
        except Exception as exc:
            self.log.exception("Exception with webserver: %s", exc)
        self.log.debug("Webserver stopped")

    @webhook
    def echo(self, incoming_request):
        """
        A simple test webhook
        """
        self.log.debug("Your incoming request is: %s", incoming_request)
        return str(incoming_request)
