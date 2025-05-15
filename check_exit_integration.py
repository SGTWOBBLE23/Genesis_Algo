#!/usr/bin/env python3
"""
Script to analyze the integration between position manager and trade exit system
"""
import os
import sys
import logging
from app import app, Trade, TradeStatus, db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if PositionManager is instantiated anywhere
try:
    from position_manager import PositionManager, Position
    import inspect
    
    logger.info("Position Manager classes loaded successfully")
    
    # Find all files that import the position manager
    import importlib.util
    import pathlib
    
    def find_importing_files():
        pm_files = []
        for file in pathlib.Path('.').glob('**/*.py'):
            if file.name != 'position_manager.py' and file.name != 'check_exit_integration.py':
                try:
                    with open(file, 'r') as f:
                        content = f.read()
                        if ('import position_manager' in content or 
                            'from position_manager' in content):
                            pm_files.append(str(file))
                except Exception as e:
                    logger.debug(f"Error reading {file}: {e}")
        return pm_files
    
    importing_files = find_importing_files()
    logger.info(f"Files importing position_manager: {importing_files}")
    
    # Check the close queue functionality
    with app.app_context():
        # Find a candidate trade for testing
        trade = db.session.query(Trade).filter_by(status=TradeStatus.OPEN).first()
        
        if trade:
            logger.info(f"Found test trade: ID={trade.id}, Symbol={trade.symbol}, Ticket={trade.ticket}")
            
            # Create test position
            pos = Position(
                symbol=trade.symbol,
                side=trade.side.value,
                entry=trade.entry or 0.0,
                sl=trade.sl or 0.0,
                tp=trade.tp or 0.0,
                qty=trade.lot or 0.1,
                open_time=0.0,
                ticket=int(trade.ticket) if trade.ticket else None
            )
            
            logger.info(f"Created test position: {pos}")
            
            # Test sending close ticket
            pos_manager = PositionManager()
            logger.info("Created PositionManager instance")
            
            # Test sending a close ticket directly
            logger.info("Testing _send_close_ticket method")
            pos_manager._send_close_ticket(pos)
            
            # Check if the API was actually called
            from mt5_ea_api import pending_closures
            logger.info(f"Pending closures after test: {pending_closures}")
            
            # Test if the right API endpoint is being called
            import requests
            from unittest.mock import patch
            
            with patch('requests.post') as mock_post:
                mock_post.return_value.ok = True
                pos_manager._send_close_ticket(pos)
                
                # Check if the right URL was called
                args, kwargs = mock_post.call_args
                logger.info(f"API endpoint called: {args[0]}")
                logger.info(f"API arguments: {kwargs.get('json')}")
                
except Exception as e:
    logger.error(f"Error testing position manager: {e}")
    import traceback
    traceback.print_exc()