from app.database import get_connection, init_db
from app.task_service import (
    create_task,
    mark_task_done,
    approve_task,
)


def setup_function():
    init_db()

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
    connection.close()

    # Create test parent and child.
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


def test_double_approval_does_not_double_reward():

    # Parent creates task.
    task_id = create_task(
        child_id=1,
        title="Finish homework",
        reward=30,
    )

    # Child marks task done.
    mark_task_done(task_id)

    # Parent approves for the first time.
    first_approval = approve_task(task_id)

    assert first_approval["status"] == "APPROVED"
    assert first_approval["reward"] == 30

    # Parent accidentally clicks approve again.
    second_approval = approve_task(task_id)

    assert second_approval["status"] == "ALREADY_APPROVED"

    # Check balance.
    connection = get_connection()

    row = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS balance
        FROM ledger
        WHERE child_id = ?
        """,
        (1,),
    ).fetchone()

    connection.close()

    # Reward must have been credited only once.
    assert row["balance"] == 30

    # There must be exactly one TASK_REWARD entry.
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM ledger
        WHERE child_id = ?
          AND type = 'TASK_REWARD'
        """,
        (1,),
    ).fetchall()

    connection.close()

    assert len(rows) == 1
    assert rows[0]["amount"] == 30