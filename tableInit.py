import sqlite3

PATH = "beer.db"

def get_connection():
    return sqlite3.connect(PATH)

#Creates tables once at the beginning
with get_connection() as connection:
        cursor = connection.cursor()

        #Create a table to track the stock of beer: beer_stock
        create_beer = """
        CREATE TABLE IF NOT EXISTS beer (
        beer_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        purchase_date DATE,
        name VARCHAR(100) NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        status TEXT CHECK(status IN('Available', 'Empty', 'Declared', 'Returned')) NOT NULL
        );
        """
        create_statiegeld = """
        CREATE TABLE IF NOT EXISTS statiegeld (
        beer_id INTEGER PRIMARY KEY NOT NULL,
        value REAL,
        FOREIGN KEY (beer_id) REFERENCES beer(beer_id)
        );
        """
        #Create a table to keep track of Free Cash Balance: balance
        create_balance = """
        CREATE TABLE IF NOT EXISTS balance (
        update_time DATETIME, 
        balance REAL NOT NULL
        );
        """

        #Create a table to track the consumption of beer: consumption
        create_consumption = """
        CREATE TABLE IF NOT EXISTS consumption (
        room_number INTEGER NOT NULL,
        beer_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        date_time DATETIME,
        FOREIGN KEY (beer_id) REFERENCES beer(beer_id)
        );
        """


        cursor.execute(create_beer)

        cursor.execute(create_statiegeld)

        cursor.execute(create_balance)

        cursor.execute(create_consumption)

        connection.commit()


