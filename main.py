import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation

from rich.console import Console
from rich.table import Table

import division

ERRORS = (ValueError, InvalidOperation, sqlite3.IntegrityError)
# markup=False: names like "[Bob]" print as-is, so nothing needs escaping.
console = Console(markup=False)


def money(cents):
    return f"EUR {cents / 100:.2f}"


def screen(title):
    console.clear()
    console.rule(f"{title}  ·  cash {money(division.get_balance())}", style="bold")


def pause():
    input("\nPress Enter to continue...")


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


# ------------------------------------------------------------------ views

def show_products():
    products = division.list_products()
    t = Table("#", "Name", title="Beers")
    for p in products:
        t.add_row(str(p["product_id"]), p["name"])
    console.print(t)
    return products


def show_people(active=None):
    people = division.list_people(active)
    if not people:
        console.print("(nobody here)")
        return people
    t = Table("#", "Name", "Status", title="People")
    for p in people:
        t.add_row(str(p["person_id"]), p["name"],
                  "active" if p["active"] else "inactive")
    console.print(t)
    return people


def show_available():
    crates = division.list_available()
    if not crates:
        console.print("(no open crates)")
        return crates
    t = Table("#", "Beer", "Bought", "Left", "Bottles", "Price", "Per bottle",
              "Deposit", title="Open crates")
    for p in crates:
        t.add_row(str(p["purchase_id"]), p["name"], p["purchased_on"],
                  str(p["remaining"]), str(p["bottles"]),
                  money(p["total_price_cents"]),
                  money(p["total_price_cents"] / p["bottles"]),
                  money(p["deposit_cents"]))
    console.print(t)
    return crates


def show_history():
    history = division.list_history()
    if not history:
        console.print("(no history)")
        return
    t = Table("Bought", "Beer", "Bottles", "Price", "Deposit", "Missing",
              title="Closed crates")
    for h in history:
        legacy = " (legacy)" if h["source"] == "legacy" else ""
        missing = h["deposit_missing_cents"] or 0
        t.add_row(h["purchased_on"], h["name"] + legacy, str(h["bottles"]),
                  money(h["total_price_cents"]), money(h["deposit_cents"]),
                  money(missing) if missing else "")
    console.print(t)


def show_owed():
    grouped = {}
    for d in division.owed_details():
        grouped.setdefault((d["person_id"], d["person"]), []).append(d)
    t = Table("#", "Person", "Crate", "Share", "Paid", "Left",
              title="Who owes what")
    for (person_id, person), rows in sorted(
            grouped.items(), key=lambda item: item[0][1].lower()):
        outstanding = sum(r["remaining"] for r in rows)
        if not outstanding:
            continue
        for i, r in enumerate(rows):
            t.add_row(str(person_id) if i == 0 else "", person if i == 0 else "",
                      f"#{r['purchase_id']} {r['product']} {r['purchased_on']}",
                      money(r["share"]), money(r["paid"]), money(r["remaining"]))
        t.add_row("", "", "Total", "", "", money(outstanding),
                  style="bold", end_section=True)
    if not t.rows:
        console.print("(nobody owes anything)")
        return
    console.print(t)


def show_balance():
    b = division.balance_sheet()
    total = b["cash"] + b["deposits"] + b["inventory"] + b["debts"]
    t = Table("Item", "Amount", title="Balance sheet")
    t.add_row("Cash", money(b["cash"]))
    t.add_row("Deposits", money(b["deposits"]))
    t.add_row("Beer stock", money(b["inventory"]))
    t.add_row("Debts", money(b["debts"]), end_section=True)
    t.add_row("Total", money(total), style="bold")
    t.add_row("Beginning", money(b["expected"]))
    if b["difference"]:
        t.add_row("MISMATCH", money(b["difference"]), style="red")
    console.print(t)


# ---------------------------------------------------------------- actions

def add_crate():
    products = show_products()
    known = {p["product_id"]: p["name"] for p in products}
    raw = input("Beer (number or new name): ").strip()
    if raw.isdigit() and int(raw) not in known:
        raise ValueError(f"Unknown beer number {raw}")
    name = known[int(raw)] if raw.isdigit() else raw
    purchased_on = ask_date("Purchase date", date.today().isoformat())
    bottles = ask_int("Bottles in crate")
    price = ask_cents("Crate price")
    deposit = ask_cents("Deposit", default=0)
    division.add_crate(name, purchased_on, bottles, price, deposit)
    console.print("Crate added.", style="green")
    balance = division.get_balance()
    if balance < 0:
        console.print(f"Warning: house cash is now negative ({money(balance)})",
                      style="yellow")


def record_drinks():
    show_people(True)
    person_id = ask_int("Person ID")
    show_available()
    purchase_id = ask_int("Purchase ID")
    bottles = ask_int("Bottles")
    consumed_on = ask_date("Date", date.today().isoformat())
    division.record_consumption(person_id, purchase_id, bottles, consumed_on)
    console.print("Consumption recorded.", style="green")


def close_crate():
    show_available()
    purchase_id = ask_int("Purchase ID")
    missing = ask_cents("Missing deposit (lost bottles/crate)", default=0)
    summary = division.purchase_summary(purchase_id, missing)
    t = Table("Person", "Bottles", "Owes",
              title=f"{summary['product']} ({summary['purchased_on']}, "
                    f"{summary['bottles']} bottles)")
    for name, bottles, cents in summary["drinkers"]:
        t.add_row(name, str(bottles), money(cents))
    t.add_row("Total to divide", "", money(summary["total_cents"]),
              style="bold", end_section=True)
    console.print(t)
    if summary["unaccounted"]:
        console.print(f"{summary['unaccounted']} unaccounted bottles split "
                      "evenly among the drinkers", style="yellow")
    if input("Close and lock? [y/N]: ").strip().lower() != "y":
        console.print("Not closed.")
        return
    division.close_purchase(purchase_id, missing)
    console.print("Crate closed and locked.", style="green")


def record_payment():
    show_owed()
    person_id = ask_int("Person ID")
    purchase_id = ask_int("Crate ID")
    remaining = division.remaining_for(person_id, purchase_id)
    if remaining <= 0:
        console.print("Nothing left to pay for this crate.")
        return
    amount = ask_cents("Payment", default=remaining)
    division.record_payment(person_id, purchase_id, amount)
    console.print("Payment recorded.", style="green")


def add_cash():
    division.add_cash(ask_cents("Cash added to the pot"))
    console.print("Cash added.", style="green")


def correct_crate():
    crates = {p["purchase_id"]: p for p in show_available()}
    purchase_id = ask_int("Purchase ID")
    crate = crates.get(purchase_id)
    if crate is None:
        raise ValueError(f"No open crate #{purchase_id}")
    console.print(" 1. Delete a 'who drank what' entry")
    console.print(" 2. Edit bottles / price / deposit")
    choice = input("Choose (1-2): ").strip()
    if choice == "1":
        entries = division.list_consumption(purchase_id)
        if not entries:
            console.print("(nothing recorded)")
            return
        t = Table("#", "Date", "Person", "Bottles",
                  title=f"Entries for crate #{purchase_id}")
        for e in entries:
            t.add_row(str(e["consumption_id"]), e["consumed_on"], e["name"],
                      str(e["bottles"]))
        console.print(t)
        division.delete_consumption(ask_int("Entry ID"))
        console.print("Entry deleted.", style="green")
    elif choice == "2":
        bottles = ask_int("Bottles in crate", crate["bottles"])
        price = ask_cents("Crate price", crate["total_price_cents"])
        deposit = ask_cents("Deposit", crate["deposit_cents"])
        division.edit_crate(purchase_id, bottles, price, deposit)
        console.print("Crate updated.", style="green")
    else:
        console.print("Choice is invalid", style="red")


def add_person():
    division.add_person(input("Person name: "))
    console.print("Person added.", style="green")


def toggle_person():
    show_people()
    person_id = ask_int("Person ID")
    active = input("Active? [y/N]: ").strip().lower() == "y"
    division.set_person_active(person_id, active)
    console.print("Person updated.", style="green")


# ------------------------------------------------------------------ menus

PEOPLE_MENU = [
    ("List active", lambda: show_people(True)),
    ("List inactive", lambda: show_people(False)),
    ("Add person", add_person),
    ("Activate / deactivate", toggle_person),
    ("Back", None),
]

MAIN_MENU = [
    ("Available beer", show_available),
    ("Beer history", show_history),
    ("People", PEOPLE_MENU),
    ("Add crate", add_crate),
    ("Record who drank what", record_drinks),
    ("Close crate", close_crate),
    ("Record payment", record_payment),
    ("Who owes what", show_owed),
    ("Balance sheet", show_balance),
    ("Add cash", add_cash),
    ("Correct open crate", correct_crate),
    ("Exit", None),
]


def run_menu(title, items):
    """Menu -> chosen action on its own screen -> pause -> back to the menu."""
    while True:
        screen(title)
        for i, (label, _) in enumerate(items, 1):
            console.print(f" {i:>2}. {label}")
        choice = input(f"\nChoose action (1-{len(items)}): ").strip()
        if not (choice.isdigit() and 1 <= int(choice) <= len(items)):
            console.print("Choice is invalid", style="red")
            pause()
            continue
        label, action = items[int(choice) - 1]
        if action is None:
            return
        if isinstance(action, list):
            run_menu(label, action)
            continue
        screen(label)
        try:
            action()
        except ERRORS as exc:
            console.print(f"Error: {exc}", style="red")
        pause()


def main():
    if division.needs_opening():
        screen("Setup")
        console.print("No house cash recorded yet.")
        division.record_opening(ask_cents("House cash before setup", default=18000))
    run_menu("BEER KING", MAIN_MENU)


if __name__ == "__main__":
    main()
