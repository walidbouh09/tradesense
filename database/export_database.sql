-- Export SQL schema for TradeSense (SQLite compatible)
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT UNIQUE,
  created_at DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE portfolios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  owner_id INTEGER,
  created_at DATETIME DEFAULT (datetime('now')),
  FOREIGN KEY(owner_id) REFERENCES users(id)
);

CREATE TABLE trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  portfolio_id INTEGER,
  symbol TEXT NOT NULL,
  qty REAL NOT NULL,
  price REAL NOT NULL,
  side TEXT NOT NULL,
  executed_at DATETIME DEFAULT (datetime('now')),
  FOREIGN KEY(portfolio_id) REFERENCES portfolios(id)
);

COMMIT;
