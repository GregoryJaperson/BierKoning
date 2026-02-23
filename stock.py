import sqlite3
import time

PATH = "beer.db"
def get_db():
    return sqlite3.connect(PATH)

#Check available stock
def get_available_stock():
    with get_db() as connection:
        cursor = connection.cursor()
        cursor.execute("""SELECT * FROM beer WHERE status = 'Available'""")
        return cursor.fetchall()

#Get beer status
def get_status(connection, beer_id):
    cursor = connection.cursor
    cursor.execute("""SELECT status FROM beer WHERE beer_id=?""")
    return cursor.fetchone[0]

#Check in-house stock
def get_every_stock():
    with get_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM beer WHERE status = 'Available' OR status='Empty''")
        return cursor.fetchall()
    
#Get old stock
def get_old_stock():
    with get_db() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM beer WHERE status='Archived' OR status='Declared")
        return cursor.fetchall()
    
#Set balance
def set_balance(connection, amount):
        cursor = connection.cursor()
        cursor.execute("INSERT INTO balance (balance, update_time) VALUES (?, ?)", (amount, time.strftime('%Y-%m-%d %H:%M:%S')))
        connection.commit()

#Get balance
def get_balance(connection):
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
        current_balance = get_balance(connection)
        set_balance(connection, current_balance - beer_price - quantity)

        connection.commit()

#Set beer empty
def set_empty(beer_id, status):
    if status not in ['Available', 'Empty']:
        raise ValueError("Invalid status. Status must be one of: 'Available', 'Empty'.")
    with get_db() as connection:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE beer SET status = ? WHERE beer_id = ?""",
            (status, beer_id)
        )
        connection.commit()


#Declare beer
def declare_beer(beer_id):
    with get_db() as connection:
        cursor = connection.cursor()

        current_status = get_status(connection, beer_id)
        if current_status == 'Declared' or current_status=='Returned':
            raise ValueError("Beer is already declared and/or returned")

        # Get beer price and add it to balance
        current_balance = get_balance(connection)
        cursor.execute("""SELECT price FROM beer WHERE beer_id=?""", beer_id)
        beer_price = cursor.fetchone()[0]
        set_balance(connection, current_balance+beer_price)

        # Mark status as declared
        cursor.execute("""UPDATE beer SET status = ? WHERE beer_id = ?""",
                       ('Declared', beer_id))

        connection.commit()



#Return beer
def return_beer(beer_id):
    with get_db() as connection:
        cursor = connection.cursor()

        current_status = get_status(connection, beer_id)
        if current_status != 'Declared':
            raise ValueError("Beer status is not 'Declared'")

        #Get statiegeld and add it to balance
        current_balance = get_balance(connection)
        cursor.execute("""SELECT value FROM statiegeld WHERE beer_id=?""", beer_id)
        statiegeld_value = cursor.fetchone()[0]
        set_balance(connection, current_balance+statiegeld_value)

        #Mark status as declared
        cursor.execute("""UPDATE beer SET status = ? WHERE beer_id = ?""",
                       ('Returned', beer_id))

        connection.commit()
