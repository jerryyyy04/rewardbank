from datetime import datetime, timezone

from app.database import get_connection


def get_balance(child_id: int) -> int:
    connection = get_connection()

    row = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS balance
        FROM ledger
        WHERE child_id = ?
        """,
        (child_id,),
    ).fetchone()

    connection.close()

    return row["balance"]


def add_ledger_entry(
    child_id: int,
    entry_type: str,
    amount: int,
    reference_id: str | None = None,
) -> int:
    connection = get_connection()

    current_balance = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS balance
        FROM ledger
        WHERE child_id = ?
        """,
        (child_id,),
    ).fetchone()["balance"]

    new_balance = current_balance + amount

    timestamp = datetime.now(timezone.utc).isoformat()

    connection.execute(
        """
        INSERT INTO ledger (
            child_id,
            type,
            amount,
            timestamp,
            reference_id,
            balance_after
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            child_id,
            entry_type,
            amount,
            timestamp,
            reference_id,
            new_balance,
        ),
    )

    connection.commit()
    connection.close()

    return new_balance