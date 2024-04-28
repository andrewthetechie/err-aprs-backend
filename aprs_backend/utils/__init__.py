from datetime import timedelta


import logging


log = logging.getLogger(__name__)


def strfdelta(tdelta: timedelta, fmt: str = "{hours:{width}}:{minutes:{width}}:{seconds:{width}}") -> str:
    """Returns a string formatted timedelta"""
    d = {
        "days": tdelta.days,
        "width": "02",
    }
    if tdelta.days > 0:
        fmt = "{days} days " + fmt

    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)
