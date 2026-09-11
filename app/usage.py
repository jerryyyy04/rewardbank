from datetime import datetime, timedelta


def calculate_usage(
    start_time: str,
    end_time: str,
    balance: int,
):
    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)

    if end <= start:
        raise ValueError("End time must be after start time")

    total_seconds = (end - start).total_seconds()
    requested_minutes = int(total_seconds / 60)

    if requested_minutes <= 0:
        raise ValueError("Usage session must be at least 1 minute")

    # Complete session can be covered.
    if balance >= requested_minutes:
        return {
            "requested_minutes": requested_minutes,
            "covered_minutes": requested_minutes,
            "rejected_minutes": 0,
            "cutoff_time": None,
        }

    # No balance available.
    if balance <= 0:
        return {
            "requested_minutes": requested_minutes,
            "covered_minutes": 0,
            "rejected_minutes": requested_minutes,
            "cutoff_time": start_time,
        }

    # Only part of the session can be covered.
    cutoff = start + timedelta(minutes=balance)

    return {
        "requested_minutes": requested_minutes,
        "covered_minutes": balance,
        "rejected_minutes": requested_minutes - balance,
        "cutoff_time": cutoff.isoformat(),
    }