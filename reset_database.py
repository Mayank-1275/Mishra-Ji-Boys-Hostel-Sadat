"""
DANGER: Wipes ALL data from the hostel database and re-seeds the 19 rooms.
Run:  python reset_database.py
It will ask you to type CONFIRM before deleting anything.
Reads connection details from .streamlit/secrets.toml
"""

import tomli
import mysql.connector

# Tables to clear, child tables first (so foreign keys don't complain).
TABLES_IN_ORDER = [
    "audit_log",
    "deposits",
    "rent_history",
    "occupancy",
    "guests",
    "expenses",
    "members",
    "rooms",
]

ROOMS = ["01", "02", "03", "04", "05", "06", "11", "12", "13", "14", "15",
         "21", "22", "23", "24", "31", "32", "33", "34"]


def main():
    # Read connection details.
    with open(".streamlit/secrets.toml", "rb") as f:
        secrets = tomli.load(f)
    db = secrets["db"]

    print("\n*** WARNING ***")
    print("This will permanently DELETE ALL DATA from the hostel database")
    print("(members, rent, guests, expenses, deposits, audit log).")
    print("Your 19 rooms will be recreated automatically.\n")

    answer = input("Type CONFIRM (in capitals) to proceed: ").strip()
    if answer != "CONFIRM":
        print("Cancelled. Nothing was deleted.")
        return

    conn = mysql.connector.connect(
        host=db["host"], port=db["port"], user=db["user"],
        password=db["password"], database=db["database"],
    )
    cursor = conn.cursor()

    print("\nClearing tables...")
    # Turn off foreign key checks so we can empty everything cleanly.
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    for table in TABLES_IN_ORDER:
        cursor.execute(f"TRUNCATE TABLE {table};")
        print(f"  cleared {table}")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

    # Re-seed the 19 rooms.
    print("Re-seeding 19 rooms...")
    cursor.executemany(
        "INSERT INTO rooms (room_no, capacity) VALUES (%s, 3)",
        [(r,) for r in ROOMS],
    )

    conn.commit()
    cursor.close()
    conn.close()
    print("\nDone. The database is now empty (rooms restored). Fresh start ready.")


if __name__ == "__main__":
    main()