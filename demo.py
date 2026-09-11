from app.database import get_connection, init_db
from app.task_service import (
    create_task,
    mark_task_done,
    approve_task,
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


def get_new_ledger_entries(before_count):
    ledger = get_ledger()
    return ledger[before_count:]


def print_step(title, before_count):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    new_entries = get_new_ledger_entries(before_count)

    if new_entries:
        print("Ledger entries created:")

        for entry in new_entries:
            print(
                f"  #{entry['id']} "
                f"{entry['type']:<15} "
                f"{entry['amount']:+4} minutes | "
                f"balance_after={entry['balance_after']} | "
                f"ref={entry['reference_id']}"
            )
    else:
        print("Ledger entries created: none")

    print(f"Current balance: {get_balance()} minutes")


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

    parent = connection.execute(
        """
        INSERT INTO parents (name, token)
        VALUES (?, ?)
        """,
        ("Demo Parent", "demo-parent-token"),
    )

    parent_id = parent.lastrowid

    connection.execute(
        """
        INSERT INTO children (name, parent_id, token)
        VALUES (?, ?, ?)
        """,
        ("Demo Child", parent_id, "demo-child-token"),
    )

    connection.commit()
    connection.close()


def assert_invariant():
    ledger = get_ledger()

    ledger_sum = sum(entry["amount"] for entry in ledger)
    balance = get_balance()

    assert ledger_sum == balance, (
        f"Ledger invariant failed: "
        f"ledger_sum={ledger_sum}, balance={balance}"
    )

    print()
    print("=" * 70)
    print("LEDGER INVARIANT")
    print("=" * 70)
    print(f"Sum of ledger amounts : {ledger_sum}")
    print(f"Current balance       : {balance}")
    print("Invariant             : PASS")


def main():
    print()
    print("#" * 70)
    print("REWARDBANK END-TO-END DEMO")
    print("#" * 70)

    # ---------------------------------------------------------
    # SETUP
    # ---------------------------------------------------------

    init_db()
    reset_database()

    print()
    print("STEP 1 — SETUP")
    print("-" * 70)
    print("Parent: Demo Parent")
    print("Child : Demo Child")
    print(f"Starting balance: {get_balance()} minutes")

    assert get_balance() == 0
    assert_invariant()

    # ---------------------------------------------------------
    # CHILD USES APPS
    # ---------------------------------------------------------

    before = len(get_ledger())

    result = report_usage(
        child_id=CHILD_ID,
        session_id="demo-session-001",
        app_id="youtube",
        start_time="2026-09-11T10:00:00+00:00",
        end_time="2026-09-11T10:10:00+00:00",
    )

    print_step(
        "STEP 2 — CHILD REPORTS 10 MINUTES OF YOUTUBE USAGE",
        before,
    )

    print(f"Usage result: {result}")

    # With zero balance, nothing can be covered.
    assert result["covered_minutes"] == 0
    assert result["rejected_minutes"] == 10
    assert result["cutoff_time"] == "2026-09-11T10:00:00+00:00"

    # No ledger entry is created because nothing was spent.
    assert get_balance() == 0
    assert_invariant()

    # ---------------------------------------------------------
    # EARN TIME
    # ---------------------------------------------------------

    before = len(get_ledger())

    task_id = create_task(
        child_id=CHILD_ID,
        title="Finish homework",
        reward=30,
    )

    print_step(
        f"STEP 3 — PARENT CREATES TASK #{task_id}",
        before,
    )

    before = len(get_ledger())

    mark_task_done(task_id)

    print_step(
        f"STEP 4 — CHILD MARKS TASK #{task_id} DONE",
        before,
    )

    before = len(get_ledger())

    approval_result = approve_task(task_id)

    print_step(
        f"STEP 5 — PARENT APPROVES TASK #{task_id}",
        before,
    )

    print(f"Approval result: {approval_result}")

    assert get_balance() == 30
    assert_invariant()

    # ---------------------------------------------------------
    # USE EARNED TIME
    # ---------------------------------------------------------

    before = len(get_ledger())

    result = report_usage(
        child_id=CHILD_ID,
        session_id="demo-session-002",
        app_id="game",
        start_time="2026-09-11T11:00:00+00:00",
        end_time="2026-09-11T11:20:00+00:00",
    )

    print_step(
        "STEP 6 — CHILD USES 20 MINUTES OF GAME TIME",
        before,
    )

    print(f"Usage result: {result}")

    assert result["covered_minutes"] == 20
    assert result["rejected_minutes"] == 0
    assert get_balance() == 10
    assert_invariant()

    # ---------------------------------------------------------
    # BALANCE HITS ZERO + EXACT CUTOFF
    # ---------------------------------------------------------

    before = len(get_ledger())

    result = report_usage(
        child_id=CHILD_ID,
        session_id="demo-session-003",
        app_id="netflix",
        start_time="2026-09-11T12:00:00+00:00",
        end_time="2026-09-11T12:30:00+00:00",
    )

    print_step(
        "STEP 7 — 30-MINUTE SESSION WITH ONLY 10 MINUTES LEFT",
        before,
    )

    print(f"Usage result: {result}")

    assert result["requested_minutes"] == 30
    assert result["covered_minutes"] == 10
    assert result["rejected_minutes"] == 20
    assert result["cutoff_time"] == "2026-09-11T12:10:00+00:00"
    assert result["balance"] == 0

    assert get_balance() == 0
    assert_invariant()

    # ---------------------------------------------------------
    # FURTHER USAGE IS BLOCKED
    # ---------------------------------------------------------

    before = len(get_ledger())

    result = report_usage(
        child_id=CHILD_ID,
        session_id="demo-session-004",
        app_id="instagram",
        start_time="2026-09-11T13:00:00+00:00",
        end_time="2026-09-11T13:05:00+00:00",
    )

    print_step(
        "STEP 8 — USAGE AFTER BALANCE REACHES ZERO",
        before,
    )

    print(f"Usage result: {result}")

    assert result["covered_minutes"] == 0
    assert result["rejected_minutes"] == 5
    assert result["cutoff_time"] == "2026-09-11T13:00:00+00:00"

    assert get_balance() == 0
    assert_invariant()

    # ---------------------------------------------------------
    # NEW TASK + APPROVAL
    # ---------------------------------------------------------

    before = len(get_ledger())

    task_id_2 = create_task(
        child_id=CHILD_ID,
        title="Clean room",
        reward=20,
    )

    print_step(
        f"STEP 9 — PARENT CREATES TASK #{task_id_2}",
        before,
    )

    before = len(get_ledger())

    mark_task_done(task_id_2)

    print_step(
        f"STEP 10 — CHILD MARKS TASK #{task_id_2} DONE",
        before,
    )

    before = len(get_ledger())

    approval_result = approve_task(task_id_2)

    print_step(
        f"STEP 11 — PARENT APPROVES TASK #{task_id_2}",
        before,
    )

    print(f"Approval result: {approval_result}")

    assert get_balance() == 20
    assert_invariant()

    # ---------------------------------------------------------
    # CHILD SPENDS SOME OF NEWLY EARNED TIME
    # ---------------------------------------------------------

    before = len(get_ledger())

    result = report_usage(
        child_id=CHILD_ID,
        session_id="demo-session-005",
        app_id="youtube",
        start_time="2026-09-11T14:00:00+00:00",
        end_time="2026-09-11T14:10:00+00:00",
    )

    print_step(
        "STEP 12 — CHILD SPENDS 10 OF THE NEWLY EARNED 20 MINUTES",
        before,
    )

    print(f"Usage result: {result}")

    assert result["covered_minutes"] == 10
    assert result["rejected_minutes"] == 0
    assert get_balance() == 10
    assert_invariant()

    # ---------------------------------------------------------
    # UNDO APPROVAL
    # ---------------------------------------------------------

    before = len(get_ledger())

    undo_result = undo_approval(task_id_2)

    print_step(
        f"STEP 13 — PARENT UNDOES APPROVAL FOR TASK #{task_id_2}",
        before,
    )

    print(f"Undo result: {undo_result}")

    # Original reward = 20.
    # Child already spent 10.
    # Only remaining 10 can be removed.
    assert undo_result["original_reward"] == 20
    assert undo_result["correction_minutes"] == 10
    assert get_balance() == 0

    assert_invariant()

    # ---------------------------------------------------------
    # FULL LEDGER
    # ---------------------------------------------------------

    print()
    print("#" * 70)
    print("STEP 14 — FULL LEDGER")
    print("#" * 70)

    for entry in get_ledger():
        print(
            f"#{entry['id']} | "
            f"{entry['type']:<15} | "
            f"{entry['amount']:+4} | "
            f"balance={entry['balance_after']} | "
            f"ref={entry['reference_id']}"
        )

    # Final invariant.
    assert_invariant()

    print()
    print("#" * 70)
    print("DEMO COMPLETE")
    print("#" * 70)
    print("All required lifecycle steps completed successfully.")
    print("Ledger invariant passed.")


if __name__ == "__main__":
    main()