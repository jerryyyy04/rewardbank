from app.database import get_connection, init_db
from app.task_service import (
    create_task,
    mark_task_done,
    approve_task,
    reject_task,
    undo_approval,
)
from app.usage_service import report_usage


CHILD_ID = 1


def get_balance():
    connection = get_connection()

    row = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS balance
        FROM ledger
        WHERE child_id = ?
        """,
        (CHILD_ID,),
    ).fetchone()

    connection.close()

    return row["balance"]


def get_ledger():
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM ledger
        WHERE child_id = ?
        ORDER BY id
        """,
        (CHILD_ID,),
    ).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def print_step(title, ledger_before):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    ledger_after = get_ledger()

    new_entries = ledger_after[len(ledger_before):]

    if new_entries:
        print("Ledger entries created:")

        for entry in new_entries:
            print(
                f"  #{entry['id']} "
                f"{entry['type']:<15} "
                f"{entry['amount']:+4} "
                f"balance_after={entry['balance_after']} "
                f"ref={entry['reference_id']}"
            )
    else:
        print("Ledger entries created: none")

    print(f"Current balance: {get_balance()} minutes")

    return ledger_after


def assert_invariant():
    ledger = get_ledger()

    ledger_total = sum(entry["amount"] for entry in ledger)
    current_balance = get_balance()

    assert ledger_total == current_balance

    print()
    print("=" * 70)
    print("LEDGER INVARIANT")
    print("=" * 70)
    print(f"Sum of ledger amounts : {ledger_total}")
    print(f"Current balance       : {current_balance}")
    print("Invariant             : PASS")


def reset_database():
    connection = get_connection()

    connection.executescript(
        """
        DELETE FROM usage_sessions;
        DELETE FROM ledger;
        DELETE FROM tasks;
        DELETE FROM children;
        DELETE FROM parents;
        """
    )

    connection.commit()

    # Create demo parent.
    parent = connection.execute(
        """
        INSERT INTO parents (name, token)
        VALUES (?, ?)
        """,
        ("Demo Parent", "demo-parent-token"),
    )

    parent_id = parent.lastrowid

    # Create demo child.
    connection.execute(
        """
        INSERT INTO children (name, parent_id, token)
        VALUES (?, ?, ?)
        """,
        ("Demo Child", parent_id, "demo-child-token"),
    )

    connection.commit()
    connection.close()


def normal_day():
    print()
    print("#" * 70)
    print("REWARDBANK - NORMAL DAY")
    print("#" * 70)

    ledger = get_ledger()

    print()
    print("Setup")
    print("-" * 70)
    print("Parent: Demo Parent")
    print("Child : Demo Child")
    print(f"Starting balance: {get_balance()} minutes")

    # ---------------------------------------------------------
    # Task 1
    # ---------------------------------------------------------

    task_id = create_task(
        child_id=CHILD_ID,
        title="Finish homework",
        reward=30,
    )

    ledger = print_step(
        f"Parent creates task #{task_id}: Finish homework (+30)",
        ledger,
    )

    mark_task_done(task_id)

    ledger = print_step(
        f"Child marks task #{task_id} as DONE",
        ledger,
    )

    result = approve_task(task_id)

    ledger = print_step(
        f"Parent approves task #{task_id}",
        ledger,
    )

    # ---------------------------------------------------------
    # Usage 1
    # ---------------------------------------------------------

    result = report_usage(
        child_id=CHILD_ID,
        session_id="normal-youtube-001",
        app_id="youtube",
        start_time="2026-09-11T10:00:00+00:00",
        end_time="2026-09-11T10:10:00+00:00",
    )

    ledger = print_step(
        "Child watches YouTube for 10 minutes",
        ledger,
    )

    print(f"Usage result: {result}")

    # ---------------------------------------------------------
    # Task 2
    # ---------------------------------------------------------

    task_id_2 = create_task(
        child_id=CHILD_ID,
        title="Clean room",
        reward=20,
    )

    ledger = print_step(
        f"Parent creates task #{task_id_2}: Clean room (+20)",
        ledger,
    )

    mark_task_done(task_id_2)

    ledger = print_step(
        f"Child marks task #{task_id_2} as DONE",
        ledger,
    )

    approve_task(task_id_2)

    ledger = print_step(
        f"Parent approves task #{task_id_2}",
        ledger,
    )

    # ---------------------------------------------------------
    # Usage 2
    # ---------------------------------------------------------

    result = report_usage(
        child_id=CHILD_ID,
        session_id="normal-game-001",
        app_id="game",
        start_time="2026-09-11T11:00:00+00:00",
        end_time="2026-09-11T11:15:00+00:00",
    )

    ledger = print_step(
        "Child plays game for 15 minutes",
        ledger,
    )

    print(f"Usage result: {result}")

    assert_invariant()


def everything_goes_wrong():
    print()
    print("#" * 70)
    print("REWARDBANK - EVERYTHING GOES WRONG")
    print("#" * 70)

    ledger = get_ledger()

    print()
    print(f"Starting balance: {get_balance()} minutes")

    # ---------------------------------------------------------
    # Task
    # ---------------------------------------------------------

    task_id = create_task(
        child_id=CHILD_ID,
        title="Emergency homework",
        reward=20,
    )

    ledger = print_step(
        f"Create task #{task_id} (+20)",
        ledger,
    )

    mark_task_done(task_id)

    ledger = print_step(
        f"Child completes task #{task_id}",
        ledger,
    )

    # First approval.
    result = approve_task(task_id)

    ledger = print_step(
        "Parent approves task",
        ledger,
    )

    print(f"First approval: {result}")

    # ---------------------------------------------------------
    # DOUBLE APPROVAL
    # ---------------------------------------------------------

    result = approve_task(task_id)

    ledger = print_step(
        "Parent accidentally approves the same task AGAIN",
        ledger,
    )

    print(f"Second approval: {result}")

    # Balance must still be 20.
    assert get_balance() == 20

    # ---------------------------------------------------------
    # TWO APPS COMPETING FOR BALANCE
    # ---------------------------------------------------------

    result = report_usage(
        child_id=CHILD_ID,
        session_id="bad-youtube-001",
        app_id="youtube",
        start_time="2026-09-11T12:00:00+00:00",
        end_time="2026-09-11T12:15:00+00:00",
    )

    ledger = print_step(
        "YouTube reports 15 minutes",
        ledger,
    )

    print(f"YouTube result: {result}")

    # Only 5 minutes remain.
    # Another app requests 10 minutes.
    result = report_usage(
        child_id=CHILD_ID,
        session_id="bad-game-001",
        app_id="game",
        start_time="2026-09-11T12:00:00+00:00",
        end_time="2026-09-11T12:10:00+00:00",
    )

    ledger = print_step(
        "Game reports 10 minutes at the same time",
        ledger,
    )

    print(f"Game result: {result}")

    # Balance should now be zero.
    assert get_balance() == 0

    # ---------------------------------------------------------
    # DUPLICATE USAGE
    # ---------------------------------------------------------

    result = report_usage(
        child_id=CHILD_ID,
        session_id="bad-game-001",
        app_id="game",
        start_time="2026-09-11T12:00:00+00:00",
        end_time="2026-09-11T12:10:00+00:00",
    )

    ledger = print_step(
        "Device retries the same usage session",
        ledger,
    )

    print(f"Duplicate usage result: {result}")

    assert get_balance() == 0

    # ---------------------------------------------------------
    # LATE OFFLINE SESSION
    # ---------------------------------------------------------

    result = report_usage(
        child_id=CHILD_ID,
        session_id="offline-session-001",
        app_id="instagram",
        start_time="2026-09-11T11:00:00+00:00",
        end_time="2026-09-11T11:20:00+00:00",
    )

    ledger = print_step(
        "Offline device reports a session from an hour ago",
        ledger,
    )

    print(f"Late session result: {result}")

    assert get_balance() == 0

    # ---------------------------------------------------------
    # USAGE AFTER ZERO
    # ---------------------------------------------------------

    result = report_usage(
        child_id=CHILD_ID,
        session_id="blocked-session-001",
        app_id="netflix",
        start_time="2026-09-11T14:00:00+00:00",
        end_time="2026-09-11T14:10:00+00:00",
    )

    ledger = print_step(
        "Another app tries to use 10 minutes with zero balance",
        ledger,
    )

    print(f"Blocked usage result: {result}")

    assert get_balance() == 0

    # ---------------------------------------------------------
    # NEW REWARD + SPEND + UNDO
    # ---------------------------------------------------------

    task_id_2 = create_task(
        child_id=CHILD_ID,
        title="Clean kitchen",
        reward=20,
    )

    ledger = print_step(
        f"Create correction task #{task_id_2} (+20)",
        ledger,
    )

    mark_task_done(task_id_2)

    ledger = print_step(
        f"Child completes task #{task_id_2}",
        ledger,
    )

    approve_task(task_id_2)

    ledger = print_step(
        f"Parent approves task #{task_id_2}",
        ledger,
    )

    # Spend half of the reward.
    result = report_usage(
        child_id=CHILD_ID,
        session_id="correction-usage-001",
        app_id="youtube",
        start_time="2026-09-11T15:00:00+00:00",
        end_time="2026-09-11T15:10:00+00:00",
    )

    ledger = print_step(
        "Child spends 10 of the newly earned 20 minutes",
        ledger,
    )

    print(f"Usage result: {result}")

    # Parent realizes wrong task was approved.
    result = undo_approval(task_id_2)

    ledger = print_step(
        f"Parent undoes approval for task #{task_id_2}",
        ledger,
    )

    print(f"Undo result: {result}")

    # Undo should remove only the 10 minutes still available.
    assert get_balance() == 0

    assert_invariant()


def main():
    print()
    print("#" * 70)
    print("REWARDBANK SIMULATOR")
    print("#" * 70)

    init_db()

    # Run normal scenario.
    reset_database()
    normal_day()

    # Run worst-case scenario.
    reset_database()
    everything_goes_wrong()

    # Final invariant.
    print()
    print("#" * 70)
    print("FINAL RESULT")
    print("#" * 70)

    assert_invariant()

    print()
    print("Simulator completed successfully.")
    print("All accounting invariants passed.")


if __name__ == "__main__":
    main()