#!/usr/bin/env python3
import app
import sys
import logging
import inspect
import position_manager

logging.basicConfig(level=logging.INFO)

print("Checking which component is responsible for managing positions...")

# Check if position_manager is used in any job in scheduler
try:
    import scheduler
    scheduler_jobs = [job.name for job in scheduler.start_scheduler().get_jobs()]
    print(f"Scheduled jobs: {scheduler_jobs}")
except Exception as e:
    print(f"Error inspecting scheduler: {e}")

# Check if the position_manager is imported in various files
print("\nChecking PositionManager usage in key files:")

def check_file_for_positionmanager(module_name):
    try:
        module = __import__(module_name)
        uses_pm = hasattr(module, 'PositionManager')
        imports_pm = 'position_manager' in sys.modules
        print(f"  {module_name}: Direct attribute: {uses_pm}, Imports module: {imports_pm}")
    except Exception as e:
        print(f"  {module_name}: Error: {e}")

# Check key modules that might use the position manager
for module in ['capture_job', 'mt5_ea_api', 'scheduler', 'app']:
    check_file_for_positionmanager(module)

# Check if api_close_ticket is used anywhere
print("\nSearching for references to close_ticket API endpoint:")
try:
    from app import app as flask_app
    for rule in flask_app.url_map.iter_rules():
        if 'close_ticket' in rule.rule:
            print(f"  Found endpoint: {rule.rule} → {rule.endpoint}")
except Exception as e:
    print(f"  Error checking Flask routes: {e}")