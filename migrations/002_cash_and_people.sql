PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ledger (
  ledger_id    INTEGER PRIMARY KEY,
  ts           TEXT NOT NULL DEFAULT (datetime('now')),
  amount_cents INTEGER NOT NULL,
  kind         TEXT NOT NULL CHECK (kind IN
                  ('opening','purchase','deposit_return','payment','topup')),
  purchase_id  INTEGER REFERENCES purchase(purchase_id),
  person_id    INTEGER REFERENCES person(person_id),
  note         TEXT
);

CREATE INDEX IF NOT EXISTS ledger_ts       ON ledger(ts);
CREATE INDEX IF NOT EXISTS ledger_purchase ON ledger(purchase_id);
CREATE INDEX IF NOT EXISTS ledger_person   ON ledger(person_id);

CREATE UNIQUE INDEX IF NOT EXISTS product_name_nocase
  ON product(name COLLATE NOCASE);
CREATE UNIQUE INDEX IF NOT EXISTS person_name_nocase
  ON person(name COLLATE NOCASE);
