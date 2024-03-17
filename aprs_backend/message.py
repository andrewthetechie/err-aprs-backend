from errbot.backends.base import Message


class APRSMessage(Message):
    @property
    def is_direct(self):
        return True
