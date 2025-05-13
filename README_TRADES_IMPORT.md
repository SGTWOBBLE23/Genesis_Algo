# Trade Import Guide

This guide explains how to import MT5 trades from Excel reports into the Genesis Trading Platform database.

## Available Scripts

- **import_trades.py**: Main import script (wrapper for import_trades_batched.py)
- **import_trades_batched.py**: Core implementation with batching and error handling
- **cleanup_duplicates.py**: Utility to remove duplicate trades

## How to Import Trades

1. **Export trades from MT5**:
   - In MetaTrader 5, go to Account History
   - Right-click and select "Save as Report"
   - Choose Excel format
   - Save the file with a name like `ReportHistory-163499.xlsx` (include account ID)

2. **Run the import script**:
   ```
   python import_trades.py path/to/ReportHistory-123456.xlsx
   ```

   Optional arguments:
   - `--account 123456`: Explicitly specify account ID
   - `--batch-size 25`: Change batch size (default: 25)

3. **Clean up duplicates** (if needed):
   ```
   python cleanup_duplicates.py --account 123456
   ```

## Features

- **Batch Processing**: Imports trades in small batches to avoid timeouts
- **Skip Existing**: Automatically skips trades already in the database
- **Error Handling**: Handles various MT5 report formats and data inconsistencies
- **Progress Tracking**: Shows real-time progress during import

## Troubleshooting

- If import stops before completion, simply run it again - it will continue where it left off
- If you see duplicate trades in the database, run the cleanup script
- For parsing errors, check if the report format has changed

## Example Workflow

Daily trade import process:
1. Export daily report from MT5
2. Run `python import_trades.py ReportHistory-163499.xlsx`
3. Periodically run `python cleanup_duplicates.py --account 163499`