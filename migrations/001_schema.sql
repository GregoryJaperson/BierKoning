PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS product (
  product_id INTEGER PRIMARY KEY,
  name       TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS person (
  person_id INTEGER PRIMARY KEY,
  name      TEXT NOT NULL UNIQUE,
  active    INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS purchase (
  purchase_id           INTEGER PRIMARY KEY,
  product_id            INTEGER NOT NULL REFERENCES product(product_id),
  purchased_on          TEXT NOT NULL
    CHECK (purchased_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  bottles               INTEGER NOT NULL CHECK (bottles > 0),
  total_price_cents     INTEGER NOT NULL CHECK (total_price_cents >= 0),
  deposit_cents         INTEGER NOT NULL DEFAULT 0 CHECK (deposit_cents >= 0),
  deposit_missing_cents INTEGER
    CHECK (deposit_missing_cents IS NULL OR deposit_missing_cents >= 0),
  closed_at             TEXT
    CHECK (closed_at IS NULL OR closed_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  CHECK ((closed_at IS NULL) = (deposit_missing_cents IS NULL))
);

CREATE TABLE IF NOT EXISTS consumption (
  consumption_id INTEGER PRIMARY KEY,
  consumed_on    TEXT NOT NULL DEFAULT (date('now'))
    CHECK (consumed_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  person_id      INTEGER NOT NULL REFERENCES person(person_id),
  purchase_id    INTEGER NOT NULL REFERENCES purchase(purchase_id),
  bottles        INTEGER NOT NULL CHECK (bottles > 0)
);

CREATE TABLE IF NOT EXISTS legacy_purchase (
  legacy_id         INTEGER PRIMARY KEY,
  product_name      TEXT NOT NULL,
  purchased_on      TEXT NOT NULL,
  bottles           INTEGER NOT NULL,
  total_price_cents INTEGER NOT NULL,
  deposit_cents     INTEGER NOT NULL,
  old_status        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS consumption_purchase ON consumption(purchase_id);
CREATE INDEX IF NOT EXISTS consumption_person   ON consumption(person_id);
CREATE INDEX IF NOT EXISTS purchase_product     ON purchase(product_id);
