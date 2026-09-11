from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.security import HTTPBearer
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

# Swagger authentication
security = HTTPBearer(auto_error=False)


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
# Authentication
# =========================

def get_authenticated_user(authorization: str | None):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization token required",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format",
        )

    token = authorization.replace("Bearer ", "", 1).strip()

    connection = get_connection()

    parent = connection.execute(
        """
        SELECT id, name
        FROM parents
        WHERE token = ?
        """,
        (token,),
    ).fetchone()

    if parent is not None:
        connection.close()

        return {
            "type": "PARENT",
            "id": parent["id"],
            "name": parent["name"],
        }

    child = connection.execute(
        """
        SELECT id, name, parent_id
        FROM children
        WHERE token = ?
        """,
        (token,),
    ).fetchone()

    connection.close()

    if child is not None:
        return {
            "type": "CHILD",
            "id": child["id"],
            "name": child["name"],
            "parent_id": child["parent_id"],
        }

    raise HTTPException(
        status_code=401,
        detail="Invalid authorization token",
    )


def require_parent(authorization: str | None):
    user = get_authenticated_user(authorization)

    if user["type"] != "PARENT":
        raise HTTPException(
            status_code=403,
            detail="Parent access required",
        )

    return user


def require_child(authorization: str | None):
    user = get_authenticated_user(authorization)

    if user["type"] != "CHILD":
        raise HTTPException(
            status_code=403,
            detail="Child access required",
        )

    return user


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

@app.post("/tasks", dependencies=[Depends(security)])
def create_task_endpoint(
    request: CreateTaskRequest,
    authorization: str | None = Header(default=None),
):
    parent = require_parent(authorization)

    connection = get_connection()

    child = connection.execute(
        """
        SELECT id, parent_id
        FROM children
        WHERE id = ?
        """,
        (request.child_id,),
    ).fetchone()

    connection.close()

    if child is None:
        raise HTTPException(
            status_code=404,
            detail="Child not found",
        )

    if child["parent_id"] != parent["id"]:
        raise HTTPException(
            status_code=403,
            detail="Parent does not own this child",
        )

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


@app.post("/tasks/{task_id}/done", dependencies=[Depends(security)])
def mark_task_done_endpoint(
    task_id: int,
    authorization: str | None = Header(default=None),
):
    child = require_child(authorization)

    connection = get_connection()

    task = connection.execute(
        """
        SELECT child_id
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    ).fetchone()

    connection.close()

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    if task["child_id"] != child["id"]:
        raise HTTPException(
            status_code=403,
            detail="Child does not own this task",
        )

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


@app.post("/tasks/{task_id}/approve", dependencies=[Depends(security)])
def approve_task_endpoint(
    task_id: int,
    authorization: str | None = Header(default=None),
):
    parent = require_parent(authorization)

    connection = get_connection()

    task = connection.execute(
        """
        SELECT
            tasks.id,
            children.parent_id
        FROM tasks
        JOIN children
            ON children.id = tasks.child_id
        WHERE tasks.id = ?
        """,
        (task_id,),
    ).fetchone()

    connection.close()

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    if task["parent_id"] != parent["id"]:
        raise HTTPException(
            status_code=403,
            detail="Parent does not own this task",
        )

    try:
        return approve_task(task_id)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@app.post("/tasks/{task_id}/reject", dependencies=[Depends(security)])
def reject_task_endpoint(
    task_id: int,
    authorization: str | None = Header(default=None),
):
    parent = require_parent(authorization)

    connection = get_connection()

    task = connection.execute(
        """
        SELECT
            tasks.id,
            children.parent_id
        FROM tasks
        JOIN children
            ON children.id = tasks.child_id
        WHERE tasks.id = ?
        """,
        (task_id,),
    ).fetchone()

    connection.close()

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    if task["parent_id"] != parent["id"]:
        raise HTTPException(
            status_code=403,
            detail="Parent does not own this task",
        )

    try:
        return reject_task(task_id)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@app.post("/tasks/{task_id}/undo", dependencies=[Depends(security)])
def undo_approval_endpoint(
    task_id: int,
    authorization: str | None = Header(default=None),
):
    parent = require_parent(authorization)

    connection = get_connection()

    task = connection.execute(
        """
        SELECT
            tasks.id,
            children.parent_id
        FROM tasks
        JOIN children
            ON children.id = tasks.child_id
        WHERE tasks.id = ?
        """,
        (task_id,),
    ).fetchone()

    connection.close()

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    if task["parent_id"] != parent["id"]:
        raise HTTPException(
            status_code=403,
            detail="Parent does not own this task",
        )

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

@app.post("/usage", dependencies=[Depends(security)])
def report_usage_endpoint(
    request: UsageRequest,
    authorization: str | None = Header(default=None),
):
    child = require_child(authorization)

    if request.child_id != child["id"]:
        raise HTTPException(
            status_code=403,
            detail="Child does not match authorization token",
        )

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

@app.get("/children/{child_id}/balance", dependencies=[Depends(security)])
def get_child_balance(
    child_id: int,
    authorization: str | None = Header(default=None),
):
    user = get_authenticated_user(authorization)

    connection = get_connection()

    child = connection.execute(
        """
        SELECT id, parent_id
        FROM children
        WHERE id = ?
        """,
        (child_id,),
    ).fetchone()

    if child is None:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Child not found",
        )

    if user["type"] == "CHILD":
        if user["id"] != child_id:
            connection.close()

            raise HTTPException(
                status_code=403,
                detail="Access denied",
            )

    elif user["type"] == "PARENT":
        if user["id"] != child["parent_id"]:
            connection.close()

            raise HTTPException(
                status_code=403,
                detail="Parent does not own this child",
            )

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

@app.get("/children/{child_id}/ledger", dependencies=[Depends(security)])
def get_child_ledger(
    child_id: int,
    authorization: str | None = Header(default=None),
):
    user = get_authenticated_user(authorization)

    connection = get_connection()

    child = connection.execute(
        """
        SELECT id, parent_id
        FROM children
        WHERE id = ?
        """,
        (child_id,),
    ).fetchone()

    if child is None:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Child not found",
        )

    if user["type"] == "CHILD":
        if user["id"] != child_id:
            connection.close()

            raise HTTPException(
                status_code=403,
                detail="Access denied",
            )

    elif user["type"] == "PARENT":
        if user["id"] != child["parent_id"]:
            connection.close()

            raise HTTPException(
                status_code=403,
                detail="Parent does not own this child",
            )

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