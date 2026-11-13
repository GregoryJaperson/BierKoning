from datetime import date
from fractions import Fraction

from db import connect


# ---------------------------------------------------------------- products

def _product_id(conn, name):
    name = name.strip()
    if not name:
        raise ValueError("Beer name cannot be empty")
    row = conn.execute(
        "SELECT product_id FROM product WHERE name = ? COLLATE NOCASE",
        (name,)).fetchone()
    if row:
        return row["product_id"]
    return conn.execute(
        "INSERT INTO product (name) VALUES (?)", (name,)).lastrowid


def list_products():
    with connect() as conn:
        return conn.execute(
            "SELECT product_id, name FROM product ORDER BY name").fetchall()


# ------------------------------------------------------------------ people

def add_person(name):
    name = name.strip()
    if not name:
        raise ValueError("Person name cannot be empty")
    with connect() as conn:
        return conn.execute(
            "INSERT INTO person (name) VALUES (?)", (name,)).lastrowid


def list_people(active=None):
    query = "SELECT person_id, name, active FROM person"
    params = ()
    if active is not None:
        query += " WHERE active = ?"
        params = (1 if active else 0,)
    with connect() as conn:
        return conn.execute(query + " ORDER BY name", params).fetchall()


def set_person_active(person_id, active):
    with connect() as conn:
        cur = conn.execute(
            "UPDATE person SET active = ? WHERE person_id = ?",
            (1 if active else 0, person_id))
        if cur.rowcount == 0:
            raise ValueError(f"Unknown person {person_id}")


# ---------------------------------------------------------------- purchases

def _purchase(conn, purchase_id):
    row = conn.execute(
        "SELECT * FROM purchase WHERE purchase_id = ?", (purchase_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown purchase {purchase_id}")
    return row


def _recorded(conn, purchase_id):
    return conn.execute("""
        SELECT COALESCE(SUM(bottles), 0) AS n
        FROM consumption WHERE purchase_id = ?
    """, (purchase_id,)).fetchone()["n"]


def add_crate(product_name, purchased_on, bottles, total_price_cents, deposit_cents=0):
    with connect() as conn:
        product_id = _product_id(conn, product_name)
        purchase_id = conn.execute("""
            INSERT INTO purchase
              (product_id, purchased_on, bottles, total_price_cents, deposit_cents)
            VALUES (?, ?, ?, ?, ?)
        """, (product_id, purchased_on, bottles, total_price_cents,
              deposit_cents)).lastrowid
        spent = total_price_cents + deposit_cents
        if spent:
            conn.execute("""
                INSERT INTO ledger (amount_cents, kind, purchase_id)
                VALUES (?, 'purchase', ?)
            """, (-spent, purchase_id))
        return purchase_id


def record_consumption(person_id, purchase_id, bottles):
    with connect() as conn:
        person = conn.execute(
            "SELECT active FROM person WHERE person_id = ?",
            (person_id,)).fetchone()
        if person is None:
            raise ValueError(f"Unknown person {person_id}")
        if not person["active"]:
            raise ValueError("Person is inactive")

        purchase = _purchase(conn, purchase_id)
        if purchase["closed_at"] is not None:
            raise ValueError("Purchase is closed and locked")
        used = _recorded(conn, purchase_id)
        if used + bottles > purchase["bottles"]:
            raise ValueError(f"Only {purchase['bottles'] - used} bottles left in this crate")

        # Local date from Python: the DB default date('now') is UTC, which
        # stamps drinks after local midnight on the day before.
        conn.execute("""
            INSERT INTO consumption (consumed_on, person_id, purchase_id, bottles)
            VALUES (?, ?, ?, ?)
        """, (date.today().isoformat(), person_id, purchase_id, bottles))


def _check_closable(conn, purchase_id, deposit_missing_cents):
    purchase = _purchase(conn, purchase_id)
    if purchase["closed_at"] is not None:
        raise ValueError("Purchase is already closed")
    if not 0 <= deposit_missing_cents <= purchase["deposit_cents"]:
        raise ValueError(
            f"Missing deposit must be 0..{purchase['deposit_cents']} cents")
    if _recorded(conn, purchase_id) == 0:
        raise ValueError("Record at least one drinker before closing")
    return purchase


def close_purchase(purchase_id, deposit_missing_cents):
    with connect() as conn:
        purchase = _check_closable(conn, purchase_id, deposit_missing_cents)
        conn.execute("""
            UPDATE purchase SET closed_at = ?, deposit_missing_cents = ?
            WHERE purchase_id = ?
        """, (date.today().isoformat(), deposit_missing_cents, purchase_id))

        returned = purchase["deposit_cents"] - deposit_missing_cents
        if returned:
            conn.execute("""
                INSERT INTO ledger (amount_cents, kind, purchase_id)
                VALUES (?, 'deposit_return', ?)
            """, (returned, purchase_id))


def _check_open_and_paid(conn, purchase_id):
    """Run after a correction; raising rolls the correction back."""
    purchase = _purchase(conn, purchase_id)
    if purchase["closed_at"] is not None:
        raise ValueError("Purchase is closed and locked")
    shares = _shares_for(conn, purchase)
    for (_, person_id), paid in _payments(conn, purchase_id).items():
        if paid > shares.get(person_id, 0):
            raise ValueError("Someone would have paid more than their share")


def list_consumption(purchase_id):
    with connect() as conn:
        return conn.execute("""
            SELECT c.consumption_id, pe.name, c.bottles
            FROM consumption c JOIN person pe USING (person_id)
            WHERE c.purchase_id = ?
            ORDER BY c.consumption_id
        """, (purchase_id,)).fetchall()


def delete_consumption(purchase_id, consumption_id):
    with connect() as conn:
        cur = conn.execute("""
            DELETE FROM consumption WHERE consumption_id = ? AND purchase_id = ?
        """, (consumption_id, purchase_id))
        if cur.rowcount == 0:
            raise ValueError(
                f"Entry #{consumption_id} is not on crate #{purchase_id}")
        _check_open_and_paid(conn, purchase_id)


def edit_crate(purchase_id, bottles, total_price_cents, deposit_cents):
    with connect() as conn:
        old = _purchase(conn, purchase_id)
        recorded = _recorded(conn, purchase_id)
        if bottles < recorded:
            raise ValueError(f"{recorded} bottles are already recorded")

        conn.execute("""
            UPDATE purchase
            SET bottles = ?, total_price_cents = ?, deposit_cents = ?
            WHERE purchase_id = ?
        """, (bottles, total_price_cents, deposit_cents, purchase_id))
        delta = (total_price_cents + deposit_cents
                 - old["total_price_cents"] - old["deposit_cents"])
        if delta:
            # Append the difference instead of rewriting the original row.
            conn.execute("""
                INSERT INTO ledger (amount_cents, kind, purchase_id, note)
                VALUES (?, 'purchase', ?, 'crate corrected')
            """, (-delta, purchase_id))
        _check_open_and_paid(conn, purchase_id)


def list_available():
    with connect() as conn:
        return conn.execute("""
            SELECT p.purchase_id, pr.name, p.purchased_on, p.bottles,
                   p.bottles - COALESCE(SUM(c.bottles), 0) AS remaining,
                   p.total_price_cents, p.deposit_cents
            FROM purchase p
            JOIN product pr USING (product_id)
            LEFT JOIN consumption c USING (purchase_id)
            WHERE p.closed_at IS NULL
            GROUP BY p.purchase_id
            ORDER BY p.purchased_on, p.purchase_id
        """).fetchall()


def list_history():
    with connect() as conn:
        return conn.execute("""
            SELECT 'crate' AS source, p.purchase_id AS id, pr.name,
                   p.purchased_on, p.bottles, p.total_price_cents,
                   p.deposit_cents, p.deposit_missing_cents
            FROM purchase p
            JOIN product pr USING (product_id)
            WHERE p.closed_at IS NOT NULL
            UNION ALL
            SELECT 'legacy', l.legacy_id, l.product_name, l.purchased_on,
                   l.bottles, l.total_price_cents, l.deposit_cents, 0
            FROM legacy_purchase l
            ORDER BY purchased_on DESC, id DESC
        """).fetchall()


# -------------------------------------------------------------------- cash

def needs_opening():
    with connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM ledger").fetchone()["n"] == 0


def record_opening(amount_cents):
    if amount_cents < 0:
        raise ValueError("Opening cash cannot be negative")
    with connect() as conn:
        has_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM ledger").fetchone()["n"]
        if has_rows:
            raise ValueError("Cash has already been recorded")
        conn.execute("""
            INSERT INTO ledger (amount_cents, kind, note)
            VALUES (?, 'opening', 'Initial house cash')
        """, (amount_cents,))


def add_cash(amount_cents, note=None):
    # Money only leaves the pot to buy crates.
    if amount_cents <= 0:
        raise ValueError("Amount must be positive")
    with connect() as conn:
        conn.execute("""
            INSERT INTO ledger (amount_cents, kind, note)
            VALUES (?, 'topup', ?)
        """, (amount_cents, note))


def get_balance():
    with connect() as conn:
        return conn.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) AS n FROM ledger"
        ).fetchone()["n"]


# ------------------------------------------------------------------ shares

def split_purchase(total_price_cents, bottles, consumed, deposit_missing_cents=None):
    """Owed cents per person. None deposit = crate still open."""
    if bottles <= 0:
        raise ValueError("bottles must be positive")
    if sum(consumed.values()) > bottles:
        raise ValueError("Consumption exceeds crate size")
    if not consumed:
        return {}

    exact = {
        person_id: Fraction(total_price_cents * qty, bottles)
        for person_id, qty in consumed.items()
    }
    if deposit_missing_cents is not None:
        unaccounted = Fraction(
            total_price_cents * (bottles - sum(consumed.values())), bottles)
        extra = (unaccounted + deposit_missing_cents) / len(consumed)
        exact = {person_id: amount + extra for person_id, amount in exact.items()}

    # Each share rounds on its own, so it only ever grows (more drinking,
    # closing); a payment made on an open crate can never end up above it.
    # The few cents this is off from the crate total show as "rounding".
    return {pid: int(amount + Fraction(1, 2)) for pid, amount in exact.items()}


def _consumed_for(conn, purchase_id):
    rows = conn.execute("""
        SELECT person_id, SUM(bottles) AS bottles
        FROM consumption WHERE purchase_id = ?
        GROUP BY person_id
    """, (purchase_id,)).fetchall()
    return {r["person_id"]: r["bottles"] for r in rows}


def _shares_for(conn, purchase):
    return split_purchase(
        purchase["total_price_cents"], purchase["bottles"],
        _consumed_for(conn, purchase["purchase_id"]),
        purchase["deposit_missing_cents"])


def _payments(conn, purchase_id=None):
    """{(purchase_id, person_id): paid cents}, optionally for one crate."""
    query = """
        SELECT purchase_id, person_id, SUM(amount_cents) AS cents
        FROM ledger WHERE kind = 'payment'
    """
    params = ()
    if purchase_id is not None:
        query += " AND purchase_id = ?"
        params = (purchase_id,)
    rows = conn.execute(query + " GROUP BY purchase_id, person_id", params)
    return {(r["purchase_id"], r["person_id"]): r["cents"] for r in rows}


# ------------------------------------------------------------------ debts

def _remaining(conn, person_id, purchase_id):
    share = _shares_for(conn, _purchase(conn, purchase_id)).get(person_id, 0)
    paid = _payments(conn, purchase_id).get((purchase_id, person_id), 0)
    return share - paid


def record_payment(person_id, purchase_id, amount_cents):
    if amount_cents <= 0:
        raise ValueError("Payment must be positive")
    with connect() as conn:
        remaining = _remaining(conn, person_id, purchase_id)
        if remaining <= 0:
            raise ValueError("Nothing left to pay for this crate")
        if amount_cents > remaining:
            raise ValueError(
                f"At most EUR {remaining / 100:.2f} is left for this crate")
        conn.execute("""
            INSERT INTO ledger (amount_cents, kind, purchase_id, person_id)
            VALUES (?, 'payment', ?, ?)
        """, (amount_cents, purchase_id, person_id))


def owed_details():
    with connect() as conn:
        purchases = conn.execute("""
            SELECT p.purchase_id, p.purchased_on, p.bottles,
                   p.total_price_cents, p.deposit_missing_cents, pr.name
            FROM purchase p
            JOIN product pr USING (product_id)
            ORDER BY p.purchased_on, p.purchase_id
        """).fetchall()
        payments = _payments(conn)
        names = {r["person_id"]: r["name"] for r in conn.execute(
            "SELECT person_id, name FROM person")}

        details = []
        for purchase in purchases:
            shares = _shares_for(conn, purchase)
            for person_id, share in shares.items():
                paid = payments.get((purchase["purchase_id"], person_id), 0)
                details.append({
                    "person_id": person_id,
                    "person": names.get(person_id, f"#{person_id}"),
                    "purchase_id": purchase["purchase_id"],
                    "product": purchase["name"],
                    "purchased_on": purchase["purchased_on"],
                    "share": share,
                    "paid": paid,
                    "remaining": share - paid,
                })
        return details


def balance_sheet():
    """Cash + deposits + beer stock + debts + rounding = opening + top-ups."""
    with connect() as conn:
        cash = conn.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) AS n FROM ledger"
        ).fetchone()["n"]
        expected = conn.execute("""
            SELECT COALESCE(SUM(amount_cents), 0) AS n
            FROM ledger WHERE kind IN ('opening', 'topup')
        """).fetchone()["n"]
        purchases = conn.execute("SELECT * FROM purchase").fetchall()
        payments = _payments(conn)

        debts = inventory = deposits = rounding = 0
        for purchase in purchases:
            shares = _shares_for(conn, purchase)
            charged = sum(shares.values())
            paid = sum(payments.get((purchase["purchase_id"], pid), 0)
                       for pid in shares)
            debts += charged - paid
            if purchase["closed_at"] is None:
                inventory += purchase["total_price_cents"] - charged
                deposits += purchase["deposit_cents"]
            else:
                rounding += (purchase["total_price_cents"]
                             + purchase["deposit_missing_cents"] - charged)

    total = cash + debts + inventory + deposits + rounding
    return {
        "cash": cash,
        "debts": debts,
        "inventory": inventory,
        "deposits": deposits,
        "rounding": rounding,
        "expected": expected,
        "difference": total - expected,
    }


def purchase_summary(purchase_id, deposit_missing_cents=0):
    """What closing this crate would charge, without closing it.

    Raises the same errors close_purchase would, before anything is shown.
    """
    with connect() as conn:
        purchase = _check_closable(conn, purchase_id, deposit_missing_cents)
        product = conn.execute(
            "SELECT name FROM product WHERE product_id = ?",
            (purchase["product_id"],)).fetchone()["name"]
        consumed = _consumed_for(conn, purchase_id)
        names = {r["person_id"]: r["name"] for r in conn.execute(
            "SELECT person_id, name FROM person")}

    shares = split_purchase(
        purchase["total_price_cents"], purchase["bottles"],
        consumed, deposit_missing_cents)
    return {
        "product": product,
        "purchased_on": purchase["purchased_on"],
        "bottles": purchase["bottles"],
        "unaccounted": purchase["bottles"] - sum(consumed.values()),
        "total_cents": purchase["total_price_cents"] + deposit_missing_cents,
        "drinkers": sorted(
            ((names[pid], qty, shares[pid]) for pid, qty in consumed.items()),
            key=lambda d: d[0].lower()),
    }
