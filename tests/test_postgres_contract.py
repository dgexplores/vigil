"""Real PostgreSQL contract test; CI supplies TEST_POSTGRES_DSN."""
import os
from pathlib import Path
import unittest
import uuid


@unittest.skipUnless(os.getenv('TEST_POSTGRES_DSN'), 'Set TEST_POSTGRES_DSN for real PostgreSQL checks')
class LedgerContractTests(unittest.TestCase):
    def test_lock_prevents_outgoing_transaction_and_migration_is_repeatable(self):
        import psycopg
        root = Path(__file__).resolve().parents[1]
        schema = root / 'bank-of-anthos/src/ledger/ledger-db/initdb/0_init_tables.sql'
        migration = root / 'vigil-system/genal_toolbox/migrations/001_account_locks.sql'
        # This test must use an isolated disposable database, never a real bank.
        with psycopg.connect(os.environ['TEST_POSTGRES_DSN'], autocommit=True) as db:
            from psycopg import sql
            name = 'vigil_test_' + uuid.uuid4().hex
            db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(name)))
            self.addCleanup(self.drop_schema, os.environ['TEST_POSTGRES_DSN'], name)
            db.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(name)))
            db.execute(schema.read_text())
            db.execute(migration.read_text())
            db.execute(migration.read_text())
            insert = "INSERT INTO transactions (from_acct,to_acct,from_route,to_route,amount,timestamp) VALUES (%s,%s,%s,%s,%s,%s)"
            args = ('0000000001','0000000002','883745000','883745000',1500,'2026-10-22 10:00:00')
            db.execute(insert,args)
            row = db.execute("INSERT INTO vigil_account_locks(account_id) VALUES (%s) RETURNING account_id", (args[0],)).fetchone()
            self.assertEqual(row[0].strip(), args[0])
            with self.assertRaises(psycopg.errors.CheckViolation):
                db.execute(insert,args)
            # Other senders and external-routing transfers remain valid.
            db.execute(insert, ('0000000003',*args[1:]))
            db.execute(insert, (args[0],args[1],'999999999',*args[3:]))
            self.assertEqual(db.execute('SELECT count(*) FROM transactions').fetchone()[0],3)
            row = db.execute("SELECT timestamp AT TIME ZONE 'UTC' FROM transactions LIMIT 1").fetchone()
            self.assertIsNotNone(row[0].tzinfo)

    @staticmethod
    def drop_schema(dsn, name):
        import psycopg
        from psycopg import sql
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(name)))
