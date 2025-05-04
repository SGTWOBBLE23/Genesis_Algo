import os
import json
import uuid
from unittest import mock
from datetime import datetime

import pytest

import capture_job


@mock.patch('capture_job.redis_client')
@mock.patch('capture_job.take_screenshot')
@mock.patch('capture_job.get_quote')
@mock.patch('capture_job.calculate_features')
@mock.patch('capture_job.uuid.uuid4')
def test_run_returns_valid_payload(mock_uuid, mock_calculate_features, mock_get_quote, 
                                mock_take_screenshot, mock_redis_client):
    # Set up mocks
    test_id = str(uuid.uuid4())
    mock_uuid.return_value = test_id
    
    test_symbol = "EURUSD"
    test_timestamp = datetime.now()
    test_iso_timestamp = test_timestamp.isoformat()
    
    test_s3_path = f"charts/{test_symbol}/test_screenshot.png"
    mock_take_screenshot.return_value = test_s3_path
    
    test_quote = {
        "bid": 1.13005,
        "ask": 1.13015,
        "spread": 0.0001,
        "timestamp": "2025-05-03T07:25:00.000000Z"
    }
    mock_get_quote.return_value = test_quote
    
    test_features = {
        "atr_1m": 0.00015,
        "spread_percentage": 0.0088
    }
    mock_calculate_features.return_value = test_features
    
    # Call the function
    result = capture_job.run(test_symbol, test_timestamp)
    
    # Verify results
    assert result is not None
    assert isinstance(result, dict)
    
    # Check all required keys are present
    expected_keys = ["id", "ts", "symbol", "image_s3", "quote", "features"]
    for key in expected_keys:
        assert key in result, f"Key '{key}' missing from result"
    
    # Check values
    assert result["id"] == test_id
    assert result["ts"] == test_iso_timestamp
    assert result["symbol"] == test_symbol
    assert result["image_s3"] == test_s3_path
    assert result["quote"] == test_quote
    assert result["features"] == test_features
    
    # Verify Redis push
    mock_redis_client.rpush.assert_called_once_with(
        "vision_queue", json.dumps(result)
    )


@mock.patch('capture_job.redis_client')
@mock.patch('capture_job.take_screenshot')
@mock.patch('capture_job.get_quote')
def test_run_handles_errors(mock_get_quote, mock_take_screenshot, mock_redis_client):
    # Set up mocks to cause an error
    test_symbol = "EURUSD"
    mock_get_quote.side_effect = Exception("Test error")
    
    # Call the function
    result = capture_job.run(test_symbol)
    
    # Verify results contains error information
    assert result is not None
    assert isinstance(result, dict)
    assert "id" in result
    assert "ts" in result
    assert "symbol" in result
    assert "error" in result
    assert "Test error" in result["error"]
    
    # Verify Redis push was not called
    mock_redis_client.rpush.assert_not_called()
