import time


def init_timestamp():
    """Build a unix style timestamp integer"""
    return int(round(time.time()))
