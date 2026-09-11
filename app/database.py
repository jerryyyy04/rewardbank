import sqlite3


DATABASE_NAME = "rewardbank.db"


def get_connection():
    connection = sqlite3.connect(
        DATABASE_NAME,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_db():
    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS parents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS children (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,

            FOREIGN KEY (parent_id)
                REFERENCES parents(id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            reward INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            approved_at TEXT,

            FOREIGN KEY (child_id)
                REFERENCES children(id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            reference_id TEXT,
            balance_after INTEGER NOT NULL,

            FOREIGN KEY (child_id)
                REFERENCES children(id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id INTEGER NOT NULL,
            session_id TEXT NOT NULL UNIQUE,
            app_id TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            requested_minutes INTEGER NOT NULL,
            covered_minutes INTEGER NOT NULL,
            rejected_minutes INTEGER NOT NULL,
            cutoff_time TEXT,

            FOREIGN KEY (child_id)
                REFERENCES children(id)
        )
        """
    )

    connection.commit()
    connection.close()