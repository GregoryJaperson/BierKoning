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


def add_product(name):
    with connect() as conn:
        return _product_id(conn, name)


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


def record_consumption(person_id, purchase_id, bottles, consumed_on=None):
    consumed_on = consumed_on or date.today().isoformat()
    with connect() as conn:
        person = conn.execute(
            "SELECT active FROM person WHERE person_id = ?",
            (person_id,)).fetchone()
        if person is None:
            raise ValueError(f"Unknown person {person_id}")
        if not person["active"]:
            raise ValueError("Person is inactive")

        purchase = conn.execute("""
            SELECT bottles, purchased_on, closed_at
            FROM purchase WHERE purchase_id = ?
        """, (purchase_id,)).fetchone()
        if purchase is None:
            raise ValueError(f"Unknown purchase {purchase_id}")
        if purchase["closed_at"] is not None:
            raise ValueError("Purchase is closed and locked")
        if consumed_on > date.today().isoformat():
            raise ValueError("Consumption date is in the future")
        if consumed_on < purchase["purchased_on"]:
            raise ValueError("Consumption date is before the purchase date")

        used = conn.execute("""
            SELECT COALESCE(SUM(bottles), 0) AS n
            FROM consumption WHERE purchase_id = ?
        """, (purchase_id,)).fetchone()["n"]
        if used + bottles > purchase["bottles"]:
            raise ValueError(f"Only {purchase['bottles'] - used} bottles left in this crate")

        conn.execute("""
            INSERT INTO consumption (consumed_on, person_id, purchase_id, bottles)
            VALUES (?, ?, ?, ?)
        """, (consumed_on, person_id, purchase_id, bottles))


def close_purchase(purchase_id, deposit_missing_cents):
    with connect() as conn:
        purchase = conn.execute("""
            SELECT deposit_cents, closed_at FROM purchase WHERE purchase_id = ?
        """, (purchase_id,)).fetchone()
        if purchase is None:
            raise ValueError(f"Unknown purchase {purchase_id}")
        if purchase["closed_at"] is not None:
            raise ValueError("Purchase is already closed")
        if not 0 <= deposit_missing_cents <= purchase["deposit_cents"]:
            raise ValueError(
                f"Missing deposit must be 0..{purchase['deposit_cents']} cents")

        recorded = conn.execute("""
            SELECT COALESCE(SUM(bottles), 0) AS n
            FROM consumption WHERE purchase_id = ?
        """, (purchase_id,)).fetchone()["n"]
        if recorded == 0:
            raise ValueError("Record at least one drinker before closing")

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
    purchase = conn.execute("""
        SELECT purchase_id, bottles, total_price_cents, deposit_missing_cents,
               closed_at
        FROM purchase WHERE purchase_id = ?
    """, (purchase_id,)).fetchone()
    if purchase is None:
        raise ValueError(f"Unknown purchase {purchase_id}")
    if purchase["closed_at"] is not None:
        raise ValueError("Purchase is closed and locked")
    shares = _shares_for(conn, purchase)
    for (pid_purchase, person_id), paid in _payments(conn).items():
        if pid_purchase == purchase_id and paid > shares.get(person_id, 0):
            raise ValueError("Someone would have paid more than their share")


def list_consumption(purchase_id):
    with connect() as conn:
        return conn.execute("""
            SELECT c.consumption_id, pe.name, c.bottles, c.consumed_on
            FROM consumption c JOIN person pe USING (person_id)
            WHERE c.purchase_id = ?
            ORDER BY c.consumed_on, c.consumption_id
        """, (purchase_id,)).fetchall()


def delete_consumption(consumption_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT purchase_id FROM consumption WHERE consumption_id = ?",
            (consumption_id,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown entry {consumption_id}")
        conn.execute("DELETE FROM consumption WHERE consumption_id = ?",
                     (consumption_id,))
        _check_open_and_paid(conn, row["purchase_id"])


def edit_crate(purchase_id, bottles, total_price_cents, deposit_cents):
    with connect() as conn:
        old = conn.execute("""
            SELECT total_price_cents, deposit_cents
            FROM purchase WHERE purchase_id = ?
        """, (purchase_id,)).fetchone()
        if old is None:
            raise ValueError(f"Unknown purchase {purchase_id}")
        recorded = conn.execute("""
            SELECT COALESCE(SUM(bottles), 0) AS n
            FROM consumption WHERE purchase_id = ?
        """, (purchase_id,)).fetchone()["n"]
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
    if deposit_missing_cents is None:
        # Round each share on its own so it never drops when someone else
        # drinks; beer stock in balance_sheet absorbs the rounding.
        return {pid: int(amount + Fraction(1, 2)) for pid, amount in exact.items()}
    else:
        unaccounted = Fraction(
            total_price_cents * (bottles - sum(consumed.values())), bottles)
        extra = (unaccounted + deposit_missing_cents) / len(consumed)
        exact = {person_id: amount + extra for person_id, amount in exact.items()}
        target = total_price_cents + deposit_missing_cents

    return _allocate(exact, target)


def _allocate(exact, target):
    """Largest remainder, so allocated cents sum to target exactly."""
    cents = {pid: amount.numerator // amount.denominator
             for pid, amount in exact.items()}
    left = target - sum(cents.values())
    order = sorted(exact, key=lambda pid: (exact[pid] - cents[pid], -pid),
                   reverse=True)
    for pid in order[:left]:
        cents[pid] += 1
    return cents


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


def _payments(conn):
    rows = conn.execute("""
        SELECT purchase_id, person_id, SUM(amount_cents) AS cents
        FROM ledger WHERE kind = 'payment'
        GROUP BY purchase_id, person_id
    """).fetchall()
    return {(r["purchase_id"], r["person_id"]): r["cents"] for r in rows}


# ------------------------------------------------------------------ debts

def _remaining(conn, person_id, purchase_id):
    purchase = conn.execute("""
        SELECT purchase_id, bottles, total_price_cents, deposit_missing_cents
        FROM purchase WHERE purchase_id = ?
    """, (purchase_id,)).fetchone()
    if purchase is None:
        raise ValueError(f"Unknown purchase {purchase_id}")
    share = _shares_for(conn, purchase).get(person_id, 0)
    paid = conn.execute("""
        SELECT COALESCE(SUM(amount_cents), 0) AS n
        FROM ledger
        WHERE kind = 'payment' AND purchase_id = ? AND person_id = ?
    """, (purchase_id, person_id)).fetchone()["n"]
    return share - paid


def remaining_for(person_id, purchase_id):
    with connect() as conn:
        return _remaining(conn, person_id, purchase_id)


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


def owed_by_person():
    totals = {}
    names = {}
    for detail in owed_details():
        person_id = detail["person_id"]
        names[person_id] = detail["person"]
        totals[person_id] = totals.get(person_id, 0) + detail["remaining"]
    return sorted(((names[pid], cents) for pid, cents in totals.items() if cents),
                  key=lambda item: item[0].lower())


def balance_sheet():
    """Cash + deposits + beer stock + debts must equal opening + top-ups."""
    with connect() as conn:
        cash = conn.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) AS n FROM ledger"
        ).fetchone()["n"]
        expected = conn.execute("""
            SELECT COALESCE(SUM(amount_cents), 0) AS n
            FROM ledger WHERE kind IN ('opening', 'topup')
        """).fetchone()["n"]
        purchases = conn.execute("""
            SELECT purchase_id, bottles, total_price_cents, deposit_cents,
                   deposit_missing_cents, closed_at
            FROM purchase
        """).fetchall()
        payments = _payments(conn)

        debts = 0
        inventory = 0
        deposits = 0
        for purchase in purchases:
            shares = _shares_for(conn, purchase)
            paid = sum(payments.get((purchase["purchase_id"], pid), 0)
                       for pid in shares)
            debts += sum(shares.values()) - paid
            if purchase["closed_at"] is None:
                inventory += purchase["total_price_cents"] - sum(shares.values())
                deposits += purchase["deposit_cents"]

    total = cash + debts + inventory + deposits
    return {
        "cash": cash,
        "debts": debts,
        "inventory": inventory,
        "deposits": deposits,
        "expected": expected,
        "difference": total - expected,
    }


def purchase_summary(purchase_id, deposit_missing_cents=0):
    """What closing this crate would charge, without closing it."""
    with connect() as conn:
        purchase = conn.execute("""
            SELECT p.purchased_on, p.bottles, p.total_price_cents,
                   pr.name AS product
            FROM purchase p JOIN product pr USING (product_id)
            WHERE p.purchase_id = ?
        """, (purchase_id,)).fetchone()
        if purchase is None:
            raise ValueError(f"Unknown purchase {purchase_id}")
        rows = conn.execute("""
            SELECT c.person_id, pe.name, SUM(c.bottles) AS bottles
            FROM consumption c JOIN person pe USING (person_id)
            WHERE c.purchase_id = ?
            GROUP BY c.person_id ORDER BY pe.name
        """, (purchase_id,)).fetchall()

    consumed = {r["person_id"]: r["bottles"] for r in rows}
    shares = split_purchase(
        purchase["total_price_cents"], purchase["bottles"],
        consumed, deposit_missing_cents)
    return {
        "product": purchase["product"],
        "purchased_on": purchase["purchased_on"],
        "bottles": purchase["bottles"],
        "unaccounted": purchase["bottles"] - sum(consumed.values()),
        "total_cents": purchase["total_price_cents"] + deposit_missing_cents,
        "drinkers": [
            (r["name"], r["bottles"], shares.get(r["person_id"], 0))
            for r in rows
        ],
    }
