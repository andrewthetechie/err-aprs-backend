from aprsd.client import KISSClient

class ErrbotKISSClient(KISSClient):
    @staticmethod
    def is_configured():
        return False
    