LEN_UNIX_TIMESTAMP_SECONDS = 10


def unix_timestamp_seconds_from_int(unix_timestamp: int) -> int:
    length_diff = len(str(unix_timestamp)) - LEN_UNIX_TIMESTAMP_SECONDS
    timestamp_seconds: int = unix_timestamp

    if length_diff > 0:
        timestamp_seconds = round(float(unix_timestamp) / float((10**length_diff)))
    elif length_diff < 0:
        timestamp_seconds = round(float(unix_timestamp) * float((10**length_diff)))

    return timestamp_seconds
