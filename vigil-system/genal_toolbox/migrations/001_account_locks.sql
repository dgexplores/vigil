-- Additive ledger enforcement for Bank of Anthos. Run once before starting agents.
BEGIN;
CREATE TABLE IF NOT EXISTS vigil_account_locks (
    account_id CHAR(10) PRIMARY KEY,
    locked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE OR REPLACE FUNCTION vigil_reject_locked_sender() RETURNS trigger AS $$
BEGIN
    IF NEW.from_route = '883745000' AND EXISTS (
        SELECT 1 FROM vigil_account_locks WHERE account_id = NEW.from_acct
    ) THEN
        RAISE EXCEPTION 'Sending account is locked by Vigil' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS vigil_account_lock_guard ON transactions;
CREATE TRIGGER vigil_account_lock_guard BEFORE INSERT ON transactions
    FOR EACH ROW EXECUTE FUNCTION vigil_reject_locked_sender();
COMMIT;
