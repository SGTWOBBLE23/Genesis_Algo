import sys
from app import app
from mt5_ea_api import pending_closures, pending_mods

with app.app_context():
    print("\nPending closures by account:")
    for account_id, tickets in pending_closures.items():
        print(f"Account {account_id}: {len(tickets)} tickets to close - {tickets}")
    
    if not pending_closures:
        print("No pending closures found.")
    
    print("\nPending modifications by account:")
    for account_id, mods in pending_mods.items():
        print(f"Account {account_id}: {len(mods)} tickets to modify - {mods}")
    
    if not pending_mods:
        print("No pending modifications found.")