from app.database import init_db, get_connection

# Create all database tables
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

child = connection.execute(
    """
    INSERT INTO children (name, parent_id, token)
    VALUES (?, ?, ?)
    """,
    ("Test Child", parent_id, "child-token"),
)

child_id = child.lastrowid

connection.commit()
connection.close()

print("Parent ID:", parent_id)
print("Child ID:", child_id)
print("Test data created successfully")