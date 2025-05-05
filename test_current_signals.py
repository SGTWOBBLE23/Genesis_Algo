import requests
import json

def get_current_signals():
    """Test the current signals API endpoint"""
    response = requests.get('http://localhost:5000/api/signals/current')
    
    if response.status_code == 200:
        signals = response.json()
        print(f"Found {len(signals)} current signals")
        
        for signal in signals:
            print(f"Signal ID: {signal['id']}")
            print(f"Symbol: {signal['symbol']}")
            print(f"Action: {signal['action']}")
            print(f"Status: {signal['status']}")
            print("---")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    get_current_signals()
