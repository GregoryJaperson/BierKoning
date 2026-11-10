import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation

import division

ERRORS = (ValueError, InvalidOperation, sqlite3.IntegrityError)


def money(cents):
    return f"EUR {cents / 100:.2f}"


def ask_int(prompt, default=None):
    hint = f" [{default}]" if default is not None else ""
    raw = input(f"{prompt}{hint}: ").strip()
    if not raw and default is not None:
        return default
    return int(raw)


def ask_date(prompt, default=None):
    hint = f" [{default}]" if default else ""
    raw = input(f"{prompt}{hint}: ").strip() or default
    date.fromisoformat(raw)
    return raw


def ask_cents(prompt, default=None):
    hint = f" [{default / 100:.2f}]" if default is not None else ""
    raw = input(f"{prompt} (EUR){hint}: ").strip()
    if not raw:
        if default is None:
            raise ValueError("Amount required")
        return default
    cents = int((Decimal(raw) * 100).quantize(Decimal("1")))
    if cents < 0:
        raise ValueError("Amount cannot be negative")
    return cents


def show_products():
    products = division.list_products()
    if products:
        print("Beers:")
    for p in products:
        print(f"  {p['product_id']}. {p['name']}")
    return products


def pick_product():
    products = show_products()
    known = {p["product_id"]: p["name"] for p in products}
    raw = input("Beer (number or new name): ").strip()
    if raw.isdigit() and int(raw) in known:
        return known[int(raw)]
    if raw.isdigit():
        raise ValueError(f"Unknown beer number {raw}")
    if not raw:
        raise ValueError("Beer name cannot be empty")
    return raw


def show_people(active=None):
    people = division.list_people(active)
    if not people:
        print("  (nobody here)")
    for p in people:
        print(f"  #{p['person_id']} {p['name']}"
              f"{'' if p['active'] else ' (inactive)'}")
    return people


def show_available():
    purchases = division.list_available()
    if not purchases:
        print("  (no open crates)")
    for p in purchases:
        per_bottle = p["total_price_cents"] / p["bottles"]
        print(f"  #{p['purchase_id']} {p['name']} {p['purchased_on']} - "
              f"{p['remaining']}/{p['bottles']} bottles, "
              f"{money(p['total_price_cents'])}, "
              f"{money(per_bottle)}/bottle, "
              f"deposit {money(p['deposit_cents'])}")
    return purchases


def show_history():
    history = division.list_history()
    if not history:
        print("  (no history)")
    for h in history:
        missing = h["deposit_missing_cents"] or 0
        tail = f", missing deposit {money(missing)}" if missing else ""
        source = " (legacy)" if h["source"] == "legacy" else ""
        print(f"  {h['purchased_on']} {h['name']}{source}: "
              f"{h['bottles']} bottles, {money(h['total_price_cents'])}, "
              f"deposit {money(h['deposit_cents'])}{tail}")


def show_owed():
    grouped = {}
    for d in division.owed_details():
        grouped.setdefault((d["person_id"], d["person"]), []).append(d)
    if not grouped:
        print("  (nobody owes anything)")
    for (person_id, person), rows in sorted(
            grouped.items(), key=lambda item: item[0][1].lower()):
        outstanding = sum(r["remaining"] for r in rows)
        if not outstanding:
            continue
        print(f"  #{person_id} {person}: {money(outstanding)}")
        for r in rows:
            print(f"    crate #{r['purchase_id']} {r['product']} "
                  f"{r['purchased_on']}: share {money(r['share'])}, "
                  f"paid {money(r['paid'])}, left {money(r['remaining'])}")


def show_balance():
    b = division.balance_sheet()
    total = b["cash"] + b["deposits"] + b["inventory"] + b["debts"]
    print(f"  Cash:          {money(b['cash'])}")
    print(f"  Deposits:      {money(b['deposits'])}")
    print(f"  Beer stock:    {money(b['inventory'])}")
    print(f"  Debts:         {money(b['debts'])}")
    print(f"  Total:         {money(total)}")
    print(f"  Beginning:     {money(b['expected'])}")
    if b["difference"]:
        print(f"  MISMATCH:      {money(b['difference'])}")


def people_menu():
    while True:
        print("\nPEOPLE")
        print("1. List active")
        print("2. List inactive")
        print("3. Add person")
        print("4. Activate / deactivate")
        print("5. Back")
        choice = input("Choose action (1-5): ").strip()
        try:
            if choice == "1":
                show_people(True)
            elif choice == "2":
                show_people(False)
            elif choice == "3":
                division.add_person(input("Person name: "))
                print("Person added.")
            elif choice == "4":
                show_people()
                person_id = ask_int("Person ID")
                active = input("Active? [y/N]: ").strip().lower() == "y"
                division.set_person_active(person_id, active)
                print("Person updated.")
            elif choice == "5":
                break
            else:
                print("Choice is invalid")
        except ERRORS as exc:
            print(f"Error: {exc}")


def correct_crate():
    print("Open crates:")
    crates = {p["purchase_id"]: p for p in show_available()}
    purchase_id = ask_int("Purchase ID")
    crate = crates.get(purchase_id)
    if crate is None:
        raise ValueError(f"No open crate #{purchase_id}")
    print("1. Delete a 'who drank what' entry")
    print("2. Edit bottles / price / deposit")
    choice = input("Choose (1-2): ").strip()
    if choice == "1":
        entries = division.list_consumption(purchase_id)
        if not entries:
            print("  (nothing recorded)")
            return
        for e in entries:
            print(f"  #{e['consumption_id']} {e['consumed_on']} "
                  f"{e['name']}: {e['bottles']} bottles")
        division.delete_consumption(ask_int("Entry ID"))
        print("Entry deleted.")
    elif choice == "2":
        bottles = ask_int("Bottles in crate", crate["bottles"])
        price = ask_cents("Crate price", crate["total_price_cents"])
        deposit = ask_cents("Deposit", crate["deposit_cents"])
        division.edit_crate(purchase_id, bottles, price, deposit)
        print("Crate updated.")
    else:
        print("Choice is invalid")


def main():
    if division.needs_opening():
        print("No house cash recorded yet.")
        opening = ask_cents("House cash before setup", default=18000)
        division.record_opening(opening)

    while True:
        print(f"\nBEER KING                      cash: {money(division.get_balance())}")
        print("1. Available beer")
        print("2. Beer history")
        print("3. People")
        print("4. Add crate")
        print("5. Record who drank what")
        print("6. Close crate")
        print("7. Record payment")
        print("8. Who owes what")
        print("9. Balance sheet")
        print("10. Add cash")
        print("11. Correct open crate")
        print("12. Exit")

        choice = input("Choose action (1-12): ").strip()

        try:
            if choice == "1":
                show_available()
            elif choice == "2":
                show_history()
            elif choice == "3":
                people_menu()
            elif choice == "4":
                name = pick_product()
                purchased_on = ask_date("Purchase date", date.today().isoformat())
                bottles = ask_int("Bottles in crate")
                price = ask_cents("Crate price")
                deposit = ask_cents("Deposit", default=0)
                division.add_crate(name, purchased_on, bottles, price, deposit)
                print("Crate added.")
                balance = division.get_balance()
                if balance < 0:
                    print(f"Warning: house cash is now negative ({money(balance)})")
            elif choice == "5":
                print("People:")
                show_people(True)
                person_id = ask_int("Person ID")
                print("Open crates:")
                show_available()
                purchase_id = ask_int("Purchase ID")
                bottles = ask_int("Bottles")
                consumed_on = ask_date("Date", date.today().isoformat())
                division.record_consumption(
                    person_id, purchase_id, bottles, consumed_on)
                print("Consumption recorded.")
            elif choice == "6":
                print("Open crates:")
                show_available()
                purchase_id = ask_int("Purchase ID")
                missing = ask_cents(
                    "Missing deposit (lost bottles/crate)", default=0)
                summary = division.purchase_summary(purchase_id, missing)
                print(f"{summary['product']} ({summary['purchased_on']}, "
                      f"{summary['bottles']} bottles)")
                if summary["drinkers"]:
                    for name, bottles, cents in summary["drinkers"]:
                        print(f"  {name}: {bottles} bottles -> {money(cents)}")
                else:
                    print("  Nobody recorded for this crate.")
                if summary["unaccounted"]:
                    print(f"  {summary['unaccounted']} unaccounted bottles "
                          "split evenly among the drinkers")
                print(f"  Total to divide: {money(summary['total_cents'])}")
                if input("Close and lock? [y/N]: ").strip().lower() != "y":
                    print("Not closed.")
                    continue
                division.close_purchase(purchase_id, missing)
                print("Crate closed and locked.")
            elif choice == "7":
                show_owed()
                person_id = ask_int("Person ID")
                purchase_id = ask_int("Crate ID")
                remaining = division.remaining_for(person_id, purchase_id)
                if remaining <= 0:
                    print("Nothing left to pay for this crate.")
                    continue
                amount = ask_cents("Payment", default=remaining)
                division.record_payment(person_id, purchase_id, amount)
                print("Payment recorded.")
            elif choice == "8":
                show_owed()
            elif choice == "9":
                show_balance()
            elif choice == "10":
                amount = ask_cents("Cash added to the pot")
                division.add_cash(amount)
                print("Cash added.")
            elif choice == "11":
                correct_crate()
            elif choice == "12":
                break
            else:
                print("Choice is invalid")
        except ERRORS as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()
