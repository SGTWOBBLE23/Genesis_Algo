#!/bin/bash

# Start the test server
echo "Starting MT5 Genesis Test Server..."
echo "This server will run in TEST MODE - no actual signals will be sent to MT5"
echo ""

# Run the test server on port 5001 (different from production)
python main_test.py