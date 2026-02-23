import sqlite3
import reads

#Set balance money
def set_balance(connection,amount):
    cursor = connection.cursor()
    cursor.execute("""INSERT INTO balance (amount) VALUES (?)""", (amount,))
    connection.commit()


#Action of buying beers
def buy (connection, brand, beer_price, bottle_amount, statiegeld, delivery):
    cursor = connection.cursor()

    #Insert the new beers to the stock table
    cursor.execute("""
        INSERT INTO beer_stock (brand, price, amount, statiegeld) VALUES (?,?,?,?);""",
        (brand, beer_price, bottle_amount, statiegeld) 
    )

    #Decrease the balance
    cursor.execute("""
        UPDATE balance SET amount = amount - (?) - (?) - (?) WHERE num = 1""",
        (beer_price, statiegeld, delivery)
    )

    connection.commit()

#Action of getting the money back for the beers
def sell (connection, id):
    cursor = connection.cursor()

    #Price of beer[id]
    cursor.execute("SELECT price FROM beer_stock WHERE id = ?", (id,))
    this_price = cursor.fetchone()

    #Add the price of beer back to balance
    cursor.execute("""
        UPDATE balance SET amount = amount + (?) WHERE num = 1""",
        (this_price[0],)
    )
    
    #Mark this crate as empty
    cursor.execute("""
        UPDATE beer_stock SET empty = 1 WHERE id=(?)""",
        (id,)
    )

    connection.commit()

#Action of getting the money back for the crate and bottles
def get_statiegeld(connection, id):
    cursor = connection.cursor()
    #Takes money of statiegeld from beer[id]
    cursor.execute("SELECT statiegeld FROM beer_stock WHERE id = ?", (id,))
    this_statiegeld = cursor.fetchone()[0]

    #Add statiegeld gotten to balance
    cursor.execute("""
        UPDATE balance SET amount = amount + (?) WHERE num = 1""",
        (this_statiegeld,)
    )
    
    #Update the statiegeld property to 1(True)
    cursor.execute("""
        UPDATE beer_stock SET got_statiegeld = 1 WHERE id = ?""",
        (id,)
    )
    
    connection.commit()
    
