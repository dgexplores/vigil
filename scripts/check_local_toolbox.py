"""Validate the original Go Toolbox HTTP contract against synthetic local data.

Start Toolbox + disposable PostgreSQL with the source schemas/migration first.
This command deliberately accepts only a localhost URL and a synthetic account.
"""
import argparse
import json
from urllib.parse import urlparse
import requests

parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--account', default='0000000001')
args = parser.parse_args()
if urlparse(args.url).hostname not in {'127.0.0.1', 'localhost', '::1'}:
    parser.error('Only a local disposable demonstration service is supported')

def invoke(tool, payload):
    response = requests.post(args.url.rstrip('/') + '/api/tool/' + tool + '/invoke', json=payload, timeout=10)
    response.raise_for_status()
    envelope = response.json()
    assert 'error' not in envelope, envelope
    rows = envelope['result']
    return json.loads(rows) if isinstance(rows, str) else rows

transactions = invoke('get_new_transactions', {'last_timestamp':'1970-01-01T00:00:00+00:00'})
assert transactions, 'Seed a synthetic transaction first'
profile = invoke('get_user_details_by_account', {'account_id':args.account})
assert profile and profile[0]['account_id'] == args.account
history = invoke('get_user_transaction_history', {'account_id':args.account})
assert history
lock = invoke('lock_account', {'account_id':args.account})
assert lock and lock[0]['account_id'] == args.account
print('PASS: transaction polling, profile lookup, transaction history, account lock via Go Toolbox HTTP')
