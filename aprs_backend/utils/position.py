from math import floor


def degrees_to_ddm(dd):
    degrees = int(floor(dd))
    minutes = (dd - degrees) * 60
    return (degrees, minutes)


def latitude_to_ddm(dd):
    direction = "S" if dd < 0 else "N"
    degrees, minutes = degrees_to_ddm(abs(dd))

    return "{:02d}{:05.2f}{}".format(
        degrees,
        minutes,
        direction,
    )


def longitude_to_ddm(dd):
    direction = "W" if dd < 0 else "E"
    degrees, minutes = degrees_to_ddm(abs(dd))

    return "{:03d}{:05.2f}{}".format(
        degrees,
        minutes,
        direction,
    )
