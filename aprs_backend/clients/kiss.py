from aprsd.client import KISSClient


class KISSClient(KISSClient):
    @staticmethod
    def is_configured():
        return False
