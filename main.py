import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation

from rich.console import Console
from rich.table import Table

import division
import migrate

ERRORS = (ValueError, InvalidOperation, sqlite3.IntegrityError)
# markup=False: names like "[Bob]" print as-is, so nothing needs escaping.
console = Console(markup=False)


def money(cents):
    return f"EUR {cents / 100:.2f}"


def crates_panel():
    """Compact open-crates table that every screen shows."""
    crates = division.list_available()
    if not crates:
        return "(no open crates)"
    t = Table("#", "Beer", "Left", "Per bottle", title="Open crates")
    for p in crates:
        t.add_row(str(p["purchase_id"]), p["name"],
                  f"{p['remaining']}/{p['bottles']}",
                  money(p["total_price_cents"] / p["bottles"]))
    return t


def screen(title, beside=None):
    """Clear, header, open crates: next to `beside` (the menu) or on top."""
    console.clear()
    console.rule(f"{title}  ·  cash {money(division.get_balance())}", style="bold")
    if beside is None:
        console.print(crates_panel())
        return
    grid = Table.grid(padding=(0, 4))
    grid.add_row(beside, crates_panel())
    console.print(grid)


def pause():
    input("\nPress Enter to continue...")


def ask(prompt, parse, valid=None):
    """Re-prompt until the answer parses and, if `valid` is given, is in it."""
    while True:
        try:
            value = parse(input(prompt).strip())
        except ERRORS as exc:
            console.print(f"{exc}. Try again.", style="red")
            continue
        if valid is None or value in valid:
            return value
        if isinstance(valid, range):
            console.print(f"Enter a number from {valid.start} to {valid.stop - 1}.",
                          style="red")
        else:
            console.print(f"#{value} does not exist. Pick one from the list.",
                          style="red")


def ask_int(prompt, default=None, valid=None):
    hint = f" [{default}]" if default is not None else ""

    def parse(raw):
        if not raw and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            raise ValueError("Not a whole number") from None

    return ask(f"{prompt}{hint}: ", parse, valid)


def ask_date(prompt, default=None):
    hint = f" [{default}]" if default else ""

    def parse(raw):
        try:
            return date.fromisoformat(raw or default).isoformat()  # 20261101 -> 2026-11-01
        except (TypeError, ValueError):
            raise ValueError("Not a date, use YYYY-MM-DD") from None

    return ask(f"{prompt}{hint}: ", parse)


def ask_cents(prompt, default=None, maximum=None):
    hint = f" [{default / 100:.2f}]" if default is not None else ""

    def parse(raw):
        if not raw:
            if default is None:
                raise ValueError("Amount required")
            return default
        try:
            cents = int((Decimal(raw) * 100).quantize(Decimal("1")))
        except InvalidOperation:
            raise ValueError("Not an amount, use e.g. 12.50") from None
        if cents < 0:
            raise ValueError("Amount cannot be negative")
        if maximum is not None and cents > maximum:
            raise ValueError(f"At most {money(maximum)}")
        return cents

    return ask(f"{prompt} (EUR){hint}: ", parse)


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
    total = (b["cash"] + b["deposits"] + b["inventory"] + b["debts"]
             + b["rounding"])
    t = Table("Item", "Amount", title="Balance sheet")
    t.add_row("Cash", money(b["cash"]))
    t.add_row("Deposits", money(b["deposits"]))
    t.add_row("Beer stock", money(b["inventory"]))
    t.add_row("Debts", money(b["debts"]))
    t.add_row("Rounding", money(b["rounding"]), end_section=True)
    t.add_row("Total", money(total), style="bold")
    t.add_row("Beginning", money(b["expected"]))
    if b["difference"]:
        t.add_row("MISMATCH", money(b["difference"]), style="red")
    console.print(t)


# ---------------------------------------------------------------- actions

def add_crate():
    products = show_products()
    known = {p["product_id"]: p["name"] for p in products}

    def parse(raw):
        if raw.isdigit():
            if int(raw) not in known:
                raise ValueError(f"Beer #{raw} does not exist")
            return known[int(raw)]
        if not raw:
            raise ValueError("Beer name cannot be empty")
        return raw

    name = ask("Beer (number or new name): ", parse)
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
    people = show_people(True)
    if not people:
        return
    crates = open_crates()
    if not crates:
        return
    person_id = ask_int("Person ID", valid={p["person_id"] for p in people})
    purchase_id = ask_int("Purchase ID", valid=crates)
    bottles = ask_int("Bottles")
    division.record_consumption(person_id, purchase_id, bottles)
    console.print("Consumption recorded.", style="green")


def open_crates():
    crates = {p["purchase_id"]: p for p in division.list_available()}
    if not crates:
        console.print("(no open crates)")
    return crates


def close_crate():
    crates = open_crates()
    if not crates:
        return
    purchase_id = ask_int("Purchase ID", valid=crates)
    missing = ask_cents("Missing deposit (lost bottles/crate)", default=0,
                        maximum=crates[purchase_id]["deposit_cents"])
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
    owed = {}
    for d in division.owed_details():
        if d["remaining"] > 0:
            owed.setdefault(d["person_id"], {})[d["purchase_id"]] = d["remaining"]
    if not owed:
        return
    person_id = ask_int("Person ID", valid=owed)
    purchase_id = ask_int("Crate ID", valid=owed[person_id])
    remaining = owed[person_id][purchase_id]
    amount = ask_cents("Payment", default=remaining, maximum=remaining)
    division.record_payment(person_id, purchase_id, amount)
    console.print("Payment recorded.", style="green")


def add_cash():
    division.add_cash(ask_cents("Cash added to the pot"))
    console.print("Cash added.", style="green")


def correct_crate():
    crates = open_crates()
    if not crates:
        return
    purchase_id = ask_int("Purchase ID", valid=crates)
    crate = crates[purchase_id]
    console.print(" 1. Delete a 'who drank what' entry")
    console.print(" 2. Edit bottles / price / deposit")
    choice = ask_int("Choose (1-2)", valid=range(1, 3))
    if choice == 1:
        entries = division.list_consumption(purchase_id)
        if not entries:
            console.print("(nothing recorded)")
            return
        t = Table("#", "Person", "Bottles",
                  title=f"Entries for crate #{purchase_id}")
        for e in entries:
            t.add_row(str(e["consumption_id"]), e["name"], str(e["bottles"]))
        console.print(t)
        entry_id = ask_int("Entry ID",
                           valid={e["consumption_id"] for e in entries})
        division.delete_consumption(purchase_id, entry_id)
        console.print("Entry deleted.", style="green")
    else:
        bottles = ask_int("Bottles in crate", crate["bottles"])
        price = ask_cents("Crate price", crate["total_price_cents"])
        deposit = ask_cents("Deposit", crate["deposit_cents"])
        division.edit_crate(purchase_id, bottles, price, deposit)
        console.print("Crate updated.", style="green")


def add_person():
    division.add_person(input("Person name: "))
    console.print("Person added.", style="green")


def toggle_person():
    people = show_people()
    if not people:
        return
    person_id = ask_int("Person ID", valid={p["person_id"] for p in people})
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
        screen(title, beside="\n".join(
            f" {i:>2}. {label}" for i, (label, _) in enumerate(items, 1)))
        choice = input(f"\nChoose action (1-{len(items)}): ").strip()
        if not (choice.isdigit() and 1 <= int(choice) <= len(items)):
            console.print("Choice is invalid", style="red")
            pause()
            continue
        label, action = items[int(choice) - 1]
        if action is None:
            return
        if isinstance(action, list):
            try:
                run_menu(label, action)
            except (KeyboardInterrupt, EOFError):  # back to this menu, not out
                pass
            continue
        screen(label)
        try:
            retry(action)
        except (KeyboardInterrupt, EOFError):  # Ctrl-C / Ctrl-D backs out
            continue
        pause()


def retry(action):
    """Rerun the action when the final save rejects the input."""
    while True:
        try:
            return action()
        except ERRORS as exc:
            console.print(f"Error: {exc}. Try again (Ctrl-C to go back).",
                          style="red")


def main():
    migrate.migrate()
    try:
        if division.needs_opening():
            screen("Setup")
            console.print("No house cash recorded yet.")
            division.record_opening(
                ask_cents("House cash before setup", default=18000))
        run_menu("BEER KING", MAIN_MENU)
    except (KeyboardInterrupt, EOFError):
        console.print("\nBye.")


if __name__ == "__main__":
    main()
