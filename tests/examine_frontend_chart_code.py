import os
import re

# Look for JavaScript files that might be displaying charts
js_files = []
for root, dirs, files in os.walk('static'):
    for file in files:
        if file.endswith('.js'):
            js_files.append(os.path.join(root, file))

# Search for signal display and chart related functionality
signal_chart_files = []
chart_timeframe_code = []

for js_file in js_files:
    try:
        with open(js_file, 'r') as f:
            content = f.read()
            
            # Look for signal-related chart display code
            if 'signal' in content.lower() and ('chart' in content.lower() or 'image' in content.lower()):
                signal_chart_files.append(js_file)
                
                # Look for timeframe-related code
                timeframe_matches = re.findall(r'(?:timeframe|time_frame|tf)[\'"\s]*[:=][\'"\s]*([\'"][\w\d]+[\'"]|\w+)', content)
                if timeframe_matches:
                    chart_timeframe_code.append({
                        'file': js_file,
                        'matches': timeframe_matches
                    })
    except Exception as e:
        print(f"Error reading {js_file}: {str(e)}")

print(f"Found {len(signal_chart_files)} JavaScript files related to signal charts:")
for file in signal_chart_files:
    print(f" - {file}")

print("\nTimeframe-related code snippets:")
for item in chart_timeframe_code:
    print(f"\nFile: {item['file']}")
    print(f"Timeframe references: {item['matches']}")

# Also check if there are any signal modal or detail views
modal_files = []
for js_file in js_files:
    try:
        with open(js_file, 'r') as f:
            content = f.read()
            if 'modal' in content.lower() and 'signal' in content.lower():
                modal_files.append(js_file)
                # Extract sections around timeframe handling
                signal_modal_sections = re.findall(r'(?:function|const|let|var)[\s]+\w+(?:\(.*?\))[\s]*\{(?:[^{}]*\{(?:[^{}]*\{[^{}]*\}[^{}]*)*\}[^{}]*)*\}', content)
                if signal_modal_sections:
                    for section in signal_modal_sections:
                        if 'signal' in section.lower() and 'timeframe' in section.lower():
                            print(f"\nPotential signal modal handler in {js_file}:")
                            print(section[:200] + "..." if len(section) > 200 else section)
    except Exception as e:
        print(f"Error reading {js_file}: {str(e)}")

# Look for template rendering of signal details
templates_with_signals = []
for root, dirs, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            try:
                with open(os.path.join(root, file), 'r') as f:
                    content = f.read()
                    if 'signal' in content.lower() and ('image' in content.lower() or 'chart' in content.lower()):
                        templates_with_signals.append(os.path.join(root, file))
            except Exception as e:
                print(f"Error reading template {file}: {str(e)}")

print(f"\nFound {len(templates_with_signals)} templates with signal visualization:")
for template in templates_with_signals:
    print(f" - {template}")

# Check frontend API calls in JavaScript
api_calls = []
for js_file in js_files:
    try:
        with open(js_file, 'r') as f:
            content = f.read()
            if '/api/signals' in content or 'api/chart' in content:
                api_calls.append({
                    'file': js_file,
                    'endpoints': re.findall(r'/api/(?:signals|chart)[^\'"]*', content)
                })
    except Exception as e:
        print(f"Error reading {js_file}: {str(e)}")

print("\nAPI endpoints used in frontend:")
for item in api_calls:
    print(f"\nFile: {item['file']}")
    print(f"Endpoints: {item['endpoints']}")
