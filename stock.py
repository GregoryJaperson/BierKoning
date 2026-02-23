from dbm import sqlite3
from time import time

PATH = "beer.db"
def get_db():
    return sqlite3.connect(PATH)

#Check balance
def get_balance():
    with get_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM balance ORDER BY update_time DESC LIMIT 1")
        return (cursor.fetchone()[0])
    

#Check available stock
def get_available_stock():
    with get_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM beer WHERE status = 'Available';")
        return (cursor.fetchall())
    
#Check in-house stock
def get_every_stock():
    with get_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM beer WHERE status = 'Available' OR status='Empty''")
        return (cursor.fetchall())
    
#Get old stock
def get_old_stock():
    with get_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM beer WHERE status='Archived' OR status='Declared")
        return (cursor.fetchall())
    
#Set balance
def set_balance(amount):
    with get_db() as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO balance (balance, update_time) VALUES (?, ?)", (amount, time.strftime('%Y-%m-%d %H:%M:%S')))
        connection.commit()

#Get balance
def get_balance():
    with get_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT balance FROM balance ORDER BY update_time DESC LIMIT 1")
        result = cursor.fetchone()
        return result[0] if result else 0

#Buy beer
def buy(purchase_date ,name, beer_price, quantity, statiegeld):
    with get_db() as connection:
        cursor = connection.cursor()
        #Insert the new beers to the stock table
        cursor.execute("""
            INSERT INTO beer (name, price, quantity, status, purchase_date) VALUES (?,?,?,?,?,?);""",
            (name, beer_price, quantity, 'Available', purchase_date) 
        )

        #Set in statiegeld table
        beer_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO statiegeld (beer_id, value) VALUES (?,?);""",
            (beer_id, statiegeld)
        )

        #Decrease the balance
        cursor.execute("""
            SELECT balance FROM balance ORDER BY update_time DESC LIMIT 1""")
        current_balance = cursor.fetchone()[0]
        cursor.execute("""
            INSERT INTO balance (balance, update_time) VALUES (?, ?)""",
            (current_balance - beer_price - quantity, time.strftime('%Y-%m-%d %H:%M:%S'))
        )

        connection.commit()

#Set beer status
def set_status(id, status):
    if(status not in ['Available', 'Empty', 'Declared', 'Returned']):
        raise ValueError("Invalid status. Status must be one of: 'Available', 'Empty', 'Declared', 'Returned'.")
    with get_db() as connection:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE beer SET status = ? WHERE beer_id = ?""",
            (status, id)
        )
        connection.commit()


#Declare beer
def declare_beer(id):    
    with get_db() as connection:
        cursor = connection.cursor()
        set_status(id, 'Declared')


#Return beer
def return_beer(id):
    with get_db() as connection:
        cursor = connection.cursor()
        set_status(id, 'Returned')

