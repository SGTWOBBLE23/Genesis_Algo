"""
Main entry point for the test environment
"""
import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [TEST ENV] - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import test configuration
try:
    # This will override any necessary settings
    import config_test
    logger.info("Test configuration loaded successfully")
except ImportError:
    logger.error("Failed to load test configuration")
    sys.exit(1)

# Import regular app
try:
    from app import app
    logger.info("Application loaded in test mode")
except ImportError as e:
    logger.error(f"Failed to load application: {str(e)}")
    sys.exit(1)

# Modify app for test environment
app.config['ENV'] = 'testing'
app.config['TESTING'] = True

# Modify database URL to use test database if needed
# Uncomment the following lines to use a separate test database
# if 'DATABASE_URL' in os.environ:
#     test_db_url = os.environ['DATABASE_URL'].replace('genesis', 'genesis_test')
#     app.config['SQLALCHEMY_DATABASE_URI'] = test_db_url
#     logger.info(f"Using test database: {test_db_url}")

if __name__ == '__main__':
    # Run the app in test mode
    logger.info("Starting application in TEST mode")
    app.run(host='0.0.0.0', port=5001, debug=True)