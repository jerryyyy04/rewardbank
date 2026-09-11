import os
import sqlite3

import pytest

from app.database import init_db, get_connection
from app.ledger import add_ledger_entry
from app.task_service import (
    create_task,
    mark_task_done,
    approve_task,
    reject_task,
    undo_approval,
)
from app.usage_service import report_usage


@pytest.fixture(autouse=True)
def fresh_database():
    """
    Create a fresh database for every test.
    """

    if os.path.exists("rewardbank.db"):
        os.remove("rewardbank.db")

    init_db()

    connection = get_connection()

    parent = connection.execute(
        """
        INSERT INTO parents (name, token)
        VALUES (?, ?)
        """,
        ("Test Parent", "parent-token"),
    )

    parent_id = parent.lastrowid

    connection.execute(
        """
        INSERT INTO children (name, parent_id, token)
        VALUES (?, ?, ?)
        """,
        ("Test Child", parent_id, "child-token"),
    )

    connection.commit()
    connection.close()

    yield

    if os.path.exists("rewardbank.db"):
        os.remove("rewardbank.db")


def get_balance(child_id=1):
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


def get_ledger(child_id=1):
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM ledger
        WHERE child_id = ?
        ORDER BY id
        """,
        (child_id,),
    ).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def test_ledger_invariant_complex_sequence():

    # Create task
    task_id = create_task(
        child_id=1,
        title="Homework",
        reward=30,
    )

    # Child completes task
    mark_task_done(task_id)

    # Parent approves
    approve_task(task_id)

    assert get_balance() == 30

    # Child uses 10 minutes
    result = report_usage(
        child_id=1,
        session_id="session-1",
        app_id="youtube",
        start_time="2026-09-10T10:00:00+00:00",
        end_time="2026-09-10T10:10:00+00:00",
    )

    assert result["covered_minutes"] == 10
    assert result["rejected_minutes"] == 0
    assert get_balance() == 20

    # Child uses another 30 minutes.
    # Only 20 can be covered.
    result = report_usage(
        child_id=1,
        session_id="session-2",
        app_id="netflix",
        start_time="2026-09-10T11:00:00+00:00",
        end_time="2026-09-10T11:30:00+00:00",
    )

    assert result["covered_minutes"] == 20
    assert result["rejected_minutes"] == 10
    assert result["cutoff_time"] == "2026-09-10T11:20:00+00:00"
    assert get_balance() == 0

    # Duplicate usage must not spend again.
    duplicate = report_usage(
        child_id=1,
        session_id="session-2",
        app_id="netflix",
        start_time="2026-09-10T11:00:00+00:00",
        end_time="2026-09-10T11:30:00+00:00",
    )

    assert duplicate["status"] == "ALREADY_PROCESSED"
    assert get_balance() == 0

    # New task
    task_id_2 = create_task(
        child_id=1,
        title="Clean room",
        reward=20,
    )

    mark_task_done(task_id_2)

    approve_task(task_id_2)

    assert get_balance() == 20

    # Spend 10 minutes
    report_usage(
        child_id=1,
        session_id="session-3",
        app_id="youtube",
        start_time="2026-09-10T13:00:00+00:00",
        end_time="2026-09-10T13:10:00+00:00",
    )

    assert get_balance() == 10

    # Undo approval.
    # Only 10 minutes remain, so only 10 can be removed.
    undo_result = undo_approval(task_id_2)

    assert undo_result["status"] == "REVOKED"
    assert undo_result["original_reward"] == 20
    assert undo_result["correction_minutes"] == 10
    assert undo_result["balance"] == 0

    # Verify ledger invariant.
    ledger = get_ledger()

    total = sum(entry["amount"] for entry in ledger)

    assert total == get_balance()
    assert total == 0


def test_approve_is_idempotent():

    task_id = create_task(
        child_id=1,
        title="Homework",
        reward=30,
    )

    mark_task_done(task_id)

    # First approval
    first = approve_task(task_id)

    assert first["status"] == "APPROVED"
    assert first["reward"] == 30
    assert get_balance() == 30

    # Second approval.
    # Simulates parent double-click.
    second = approve_task(task_id)

    assert second["status"] == "ALREADY_APPROVED"

    # Reward must NOT be added again.
    assert get_balance() == 30

    ledger = get_ledger()

    reward_entries = [
        entry
        for entry in ledger
        if entry["type"] == "TASK_REWARD"
    ]

    assert len(reward_entries) == 1
    assert reward_entries[0]["amount"] == 30


def test_duplicate_usage_is_idempotent():

    task_id = create_task(
        child_id=1,
        title="Homework",
        reward=30,
    )

    mark_task_done(task_id)
    approve_task(task_id)

    first = report_usage(
        child_id=1,
        session_id="same-session",
        app_id="youtube",
        start_time="2026-09-10T10:00:00+00:00",
        end_time="2026-09-10T10:10:00+00:00",
    )

    assert first["covered_minutes"] == 10
    assert get_balance() == 20

    second = report_usage(
        child_id=1,
        session_id="same-session",
        app_id="youtube",
        start_time="2026-09-10T10:00:00+00:00",
        end_time="2026-09-10T10:10:00+00:00",
    )

    assert second["status"] == "ALREADY_PROCESSED"

    # Must still be 20.
    assert get_balance() == 20