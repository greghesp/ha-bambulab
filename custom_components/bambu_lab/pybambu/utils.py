def search(lst, predicate, default=None):
    """Search an array for a string"""
    for item in lst:
        if predicate(item):
            return item
    return default


def fan_percentage(speed):
    """Converts a fan speed to percentage"""
    return round((int(speed) / 15) * 100)
