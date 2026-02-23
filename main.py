import time

import stock
import sys

from stock import declare_beer


def main():
    while True:
        print("\nBEER KING MENU")
        print("1. Check balance")
        print("2. Check inventory")
        print("3. Input purchase")
        print("4. Mark beer empty")
        print("5. Decla beer cost")
        print("6. Return statiegeld")
        print("7. Exit")

        choice = input("Choose action(1-7): ")

        if choice == '1':
            print(stock.get_balance(stock.get_db()))
        elif choice == '2':
            print(stock.get_available_stock())
        elif choice == '3':
            purchase_date = input("Purchase date(YYYY-mm-dd):")
            beer_name = input("Beer name: ")
            price = float(input("Beer price (exl. statiegeld): "))
            qty = int(input("Beer quantity: "))
            sg = float(input("Total statiegeld (& other returnables): "))
            stock.buy(purchase_date, beer_name, price, qty, sg)
            print("Noted: ?, ?, ?, ?", beer_name, price, qty, sg)
        elif choice == '4':
            beer_id = int(input("Beer ID: "))
            stock.set_empty(beer_id, 'Empty')
        elif choice == '5':
            beer_id = int(input("Beer ID: "))
            declare_beer(beer_id)
        elif choice == '6':
            beer_id = int(input("Beer ID: "))
            stock.return_beer(beer_id)
        elif choice == '7':
            break
        else:
            print("Choice is invalid")
            continue

if __name__ == "__main__":
    main()

