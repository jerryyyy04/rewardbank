from datetime import datetime, timezone

from app.database import get_connection
from app.ledger import add_ledger_entry


def create_task(child_id: int, title: str, reward: int):
    if reward <= 0:
        raise ValueError("Reward must be greater than 0")

    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT INTO tasks (
            child_id,
            title,
            reward,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            child_id,
            title,
            reward,
            "CREATED",
            datetime.now(timezone.utc).isoformat(),
        ),
    )

    task_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return task_id


def mark_task_done(task_id: int):
    connection = get_connection()

    task = connection.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    ).fetchone()

    if task is None:
        connection.close()
        raise ValueError("Task not found")

    if task["status"] != "CREATED":
        connection.close()
        raise ValueError(
            f"Task cannot be marked done from status {task['status']}"
        )

    connection.execute(
        """
        UPDATE tasks
        SET status = ?
        WHERE id = ?
        """,
        ("DONE", task_id),
    )

    connection.commit()
    connection.close()


def approve_task(task_id: int):
    connection = get_connection()

    task = connection.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    ).fetchone()

    if task is None:
        connection.close()
        raise ValueError("Task not found")

    if task["status"] == "APPROVED":
        connection.close()
        return {
            "status": "ALREADY_APPROVED",
            "reward": task["reward"],
        }

    if task["status"] != "DONE":
        connection.close()
        raise ValueError(
            f"Task cannot be approved from status {task['status']}"
        )

    connection.execute(
        """
        UPDATE tasks
        SET status = ?,
            approved_at = ?
        WHERE id = ?
        """,
        (
            "APPROVED",
            datetime.now(timezone.utc).isoformat(),
            task_id,
        ),
    )

    connection.commit()
    connection.close()

    new_balance = add_ledger_entry(
        child_id=task["child_id"],
        entry_type="TASK_REWARD",
        amount=task["reward"],
        reference_id=f"task-{task_id}",
    )

    return {
        "status": "APPROVED",
        "reward": task["reward"],
        "balance": new_balance,
    }


def reject_task(task_id: int):
    connection = get_connection()

    task = connection.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    ).fetchone()

    if task is None:
        connection.close()
        raise ValueError("Task not found")

    if task["status"] == "REJECTED":
        connection.close()
        return {
            "status": "ALREADY_REJECTED"
        }

    if task["status"] != "DONE":
        connection.close()
        raise ValueError(
            f"Task cannot be rejected from status {task['status']}"
        )

    connection.execute(
        """
        UPDATE tasks
        SET status = ?
        WHERE id = ?
        """,
        ("REJECTED", task_id),
    )

    connection.commit()
    connection.close()

    return {
        "status": "REJECTED"
    }


def undo_approval(task_id: int):
    connection = get_connection()

    task = connection.execute(
        """
        SELECT *
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    ).fetchone()

    if task is None:
        connection.close()
        raise ValueError("Task not found")

    if task["status"] == "REVOKED":
        connection.close()
        return {
            "status": "ALREADY_REVOKED"
        }

    if task["status"] != "APPROVED":
        connection.close()
        raise ValueError(
            f"Task cannot be undone from status {task['status']}"
        )

    # Find how much of this reward is still available.
    reward_entry = connection.execute(
        """
        SELECT amount
        FROM ledger
        WHERE child_id = ?
          AND type = 'TASK_REWARD'
          AND reference_id = ?
        ORDER BY id
        LIMIT 1
        """,
        (
            task["child_id"],
            f"task-{task_id}",
        ),
    ).fetchone()

    if reward_entry is None:
        connection.close()
        raise ValueError("Reward ledger entry not found")

    reward = reward_entry["amount"]

    # Current balance
    balance_row = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS balance
        FROM ledger
        WHERE child_id = ?
        """,
        (task["child_id"],),
    ).fetchone()

    current_balance = balance_row["balance"]

    # We never allow the balance to become negative.
    correction_amount = min(reward, current_balance)

    connection.execute(
        """
        UPDATE tasks
        SET status = ?
        WHERE id = ?
        """,
        ("REVOKED", task_id),
    )

    connection.commit()
    connection.close()

    if correction_amount > 0:
        new_balance = add_ledger_entry(
            child_id=task["child_id"],
            entry_type="UNDO_APPROVAL",
            amount=-correction_amount,
            reference_id=f"task-{task_id}",
        )
    else:
        new_balance = current_balance

    return {
        "status": "REVOKED",
        "original_reward": reward,
        "correction_minutes": correction_amount,
        "balance": new_balance,
    }