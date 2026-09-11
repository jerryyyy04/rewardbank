from app.database import get_connection, init_db


init_db()

connection = get_connection()

# Create parent only if it does not already exist
parent = connection.execute(
    """
    SELECT id, name, token
    FROM parents
    WHERE token = ?
    """,
    ("parent-token",),
).fetchone()

if parent is None:
    connection.execute(
        """
        INSERT INTO parents (name, token)
        VALUES (?, ?)
        """,
        ("Test Parent", "parent-token"),
    )

    connection.commit()

    parent = connection.execute(
        """
        SELECT id, name, token
        FROM parents
        WHERE token = ?
        """,
        ("parent-token",),
    ).fetchone()


# Create child only if it does not already exist
child = connection.execute(
    """
    SELECT id, name, token, parent_id
    FROM children
    WHERE token = ?
    """,
    ("child-token",),
).fetchone()

if child is None:
    connection.execute(
        """
        INSERT INTO children (name, token, parent_id)
        VALUES (?, ?, ?)
        """,
        ("Test Child", "child-token", parent["id"]),
    )

    connection.commit()

    child = connection.execute(
        """
        SELECT id, name, token, parent_id
        FROM children
        WHERE token = ?
        """,
        ("child-token",),
    ).fetchone()


connection.close()

print("Test data is ready.")
print()
print(f"Parent ID   : {parent['id']}")
print(f"Parent name : {parent['name']}")
print(f"Parent token: {parent['token']}")
print()
print(f"Child ID    : {child['id']}")
print(f"Child name  : {child['name']}")
print(f"Child token : {child['token']}")