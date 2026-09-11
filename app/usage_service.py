from datetime import datetime

from app.database import get_connection
from app.ledger import add_ledger_entry
from app.usage import calculate_usage


def report_usage(
    child_id: int,
    session_id: str,
    app_id: str,
    start_time: str,
    end_time: str,
):
    connection = get_connection()

    # Check whether this session was already processed.
    existing = connection.execute(
        """
        SELECT *
        FROM usage_sessions
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()

    if existing is not None:
        connection.close()

        return {
            "status": "ALREADY_PROCESSED",
            "session_id": session_id,
            "covered_minutes": existing["covered_minutes"],
            "rejected_minutes": existing["rejected_minutes"],
            "cutoff_time": existing["cutoff_time"],
        }

    # Get current balance.
    balance_row = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS balance
        FROM ledger
        WHERE child_id = ?
        """,
        (child_id,),
    ).fetchone()

    balance = balance_row["balance"]

    connection.close()

    # Calculate how much of the session can be covered.
    result = calculate_usage(
        start_time=start_time,
        end_time=end_time,
        balance=balance,
    )

    covered = result["covered_minutes"]

    # Calculate requested duration.
    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)

    requested_minutes = int(
        (end - start).total_seconds() / 60
    )

    # Deduct only covered minutes.
    if covered > 0:
        add_ledger_entry(
            child_id=child_id,
            entry_type="USAGE",
            amount=-covered,
            reference_id=session_id,
        )

    # Save processed usage session.
    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO usage_sessions (
                child_id,
                session_id,
                app_id,
                start_time,
                end_time,
                requested_minutes,
                covered_minutes,
                rejected_minutes,
                cutoff_time
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                child_id,
                session_id,
                app_id,
                start_time,
                end_time,
                requested_minutes,
                result["covered_minutes"],
                result["rejected_minutes"],
                result["cutoff_time"],
            ),
        )

        connection.commit()

    finally:
        connection.close()

    # Get final balance.
    connection = get_connection()

    balance_row = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS balance
        FROM ledger
        WHERE child_id = ?
        """,
        (child_id,),
    ).fetchone()

    final_balance = balance_row["balance"]

    connection.close()

    return {
        "status": "PROCESSED",
        "session_id": session_id,
        "requested_minutes": requested_minutes,
        "covered_minutes": result["covered_minutes"],
        "rejected_minutes": result["rejected_minutes"],
        "cutoff_time": result["cutoff_time"],
        "balance": final_balance,
    }