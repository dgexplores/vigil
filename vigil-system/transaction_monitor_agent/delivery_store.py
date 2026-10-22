"""Durable polling cursor and alert outbox for a single monitor worker."""
from contextlib import contextmanager
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


def timestamp(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Transaction timestamps must include a timezone')
    return parsed.astimezone(timezone.utc).isoformat()


class DeliveryStore:
    def __init__(self, path, start_timestamp='1970-01-01T00:00:00+00:00'):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS cursor (
                    id INTEGER PRIMARY KEY CHECK (id = 1), value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS deliveries (
                    transaction_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending','delivered','ignored')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                );
            ''')
            db.execute('INSERT OR IGNORE INTO cursor VALUES (1, ?)',
                       (timestamp(start_timestamp),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @property
    def checkpoint(self):
        with self.connect() as db:
            return db.execute('SELECT value FROM cursor WHERE id=1').fetchone()[0]

    def ingest(self, transactions, threshold):
        """Validate the batch, then atomically save alerts and advance the cursor."""
        rows = []
        for tx in transactions:
            tx_id = tx.get('transaction_id')
            if tx_id is None or not str(tx_id).strip():
                raise ValueError('Missing transaction_id')
            amount = float(tx['amount'])
            if not math.isfinite(amount):
                raise ValueError('Transaction amount must be finite')
            when = timestamp(tx['timestamp'])
            rows.append((str(tx_id), json.dumps(tx, allow_nan=False),
                         'pending' if amount > threshold else 'ignored', when))
        with self.connect() as db:
            # Acquire the write lock before reading the cursor.
            db.execute('BEGIN IMMEDIATE')
            latest = db.execute('SELECT value FROM cursor WHERE id=1').fetchone()[0]
            for tx_id, payload, status, when in rows:
                db.execute('INSERT OR IGNORE INTO deliveries '
                           '(transaction_id, payload, status) VALUES (?, ?, ?)',
                           (tx_id, payload, status))
                latest = max(latest, when)
            db.execute('UPDATE cursor SET value=? WHERE id=1', (latest,))

    def pending(self, limit=100):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM deliveries WHERE status='pending' "
                              'ORDER BY attempts, rowid LIMIT ?', (limit,)).fetchall()
            return [json.loads(row[0]) for row in rows]

    def record_attempt(self, tx_id, success, error=None):
        with self.connect() as db:
            db.execute("UPDATE deliveries SET attempts=attempts+1, status=?, last_error=? "
                       "WHERE transaction_id=? AND status='pending'",
                       ('delivered' if success else 'pending', None if success else str(error)[:500], str(tx_id)))

    def summary(self):
        with self.connect() as db:
            counts = {row[0]: row[1] for row in db.execute(
                'SELECT status, COUNT(*) FROM deliveries GROUP BY status')}
        return {key: counts.get(key, 0) for key in ('pending', 'delivered', 'ignored')}
