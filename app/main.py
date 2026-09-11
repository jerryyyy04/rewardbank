from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.database import init_db, get_connection
from app.task_service import (
    create_task,
    mark_task_done,
    approve_task,
    reject_task,
    undo_approval,
)
from app.usage_service import report_usage


app = FastAPI(title="RewardBank")

init_db()


# =========================
# Request Models
# =========================

class CreateTaskRequest(BaseModel):
    child_id: int
    title: str
    reward: int


class UsageRequest(BaseModel):
    child_id: int
    session_id: str
    app_id: str
    start: str
    end: str


# =========================
# Health Check
# =========================

@app.get("/")
def health_check():
    return {
        "message": "RewardBank is running"
    }


# =========================
# TASKS
# =========================

@app.post("/tasks")
def create_task_endpoint(request: CreateTaskRequest):
    try:
        task_id = create_task(
            child_id=request.child_id,
            title=request.title,
            reward=request.reward,
        )

        return {
            "task_id": task_id,
            "message": "Task created",
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@app.post("/tasks/{task_id}/done")
def mark_task_done_endpoint(task_id: int):
    try:
        mark_task_done(task_id)

        return {
            "message": "Task marked as done"
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@app.post("/tasks/{task_id}/approve")
def approve_task_endpoint(task_id: int):
    try:
        return approve_task(task_id)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@app.post("/tasks/{task_id}/reject")
def reject_task_endpoint(task_id: int):
    try:
        return reject_task(task_id)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@app.post("/tasks/{task_id}/undo")
def undo_approval_endpoint(task_id: int):
    try:
        return undo_approval(task_id)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


# =========================
# USAGE
# =========================

@app.post("/usage")
def report_usage_endpoint(request: UsageRequest):
    try:
        return report_usage(
            child_id=request.child_id,
            session_id=request.session_id,
            app_id=request.app_id,
            start_time=request.start,
            end_time=request.end,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


# =========================
# BALANCE
# =========================

@app.get("/children/{child_id}/balance")
def get_child_balance(child_id: int):
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

    return {
        "child_id": child_id,
        "balance": row["balance"],
    }


# =========================
# LEDGER
# =========================

@app.get("/children/{child_id}/ledger")
def get_child_ledger(child_id: int):
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT
            id,
            child_id,
            type,
            amount,
            timestamp,
            reference_id,
            balance_after
        FROM ledger
        WHERE child_id = ?
        ORDER BY id
        """,
        (child_id,),
    ).fetchall()

    connection.close()

    return {
        "child_id": child_id,
        "ledger": [dict(row) for row in rows],
    }