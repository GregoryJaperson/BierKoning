import sqlite3
def get_latest_balance(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM balance ORDER BY balance DESC LIMIT 1")
    print(cursor.fetchone()[0])

def get_available_stock(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM items WHERE status = 'Available';")
    print(cursor.fetchall())
    print("You have " + len(cursor.fetchall())+" beer crates left")

def get_every_stock(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM items WHERE status = 'Available' OR status='Empty' OR status='Settled'")
    print(cursor.fetchall())

