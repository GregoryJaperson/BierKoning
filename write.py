import sqlite3
import time
def set_latest_balance(connection, amount):
    cursor = connection.cursor()
    cursor.execute("INSERT INTO balance (balance, date) VALUES (?, ?)", (amount, time.strftime('%Y-%m-%d')))
    connection.commit()

def make_purchase(connection, delivery_fee, total_price):
    cursor = connection.cursor()
    cursor.execute("INSERT INTO purchases (purchase_date, delivery_fee, total_price) VALUES (?,?,?)", (time.strftime('%Y-%m-%d'), delivery_fee, total_price))
    print(cursor.fetchall())
    print("You have " + len(cursor.fetchall())+" beer crates left")

#function set empty
def set_empty(connection):
    cursor = connection.cursor()
    cursor.execute("")

def get_every_stock(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM items WHERE status = 'Available' OR status='Empty' OR status='Settled'")
    print(cursor.fetchall())
