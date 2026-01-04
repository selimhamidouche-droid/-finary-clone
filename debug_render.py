import os
import django
from django.conf import settings
from django.template import Context, Template
from django.template.loader import get_template
import sys

# Configure Django
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wealthgravity.settings")
django.setup()

from portfolio.models import AssetCategory

def test_render():
    # Mock data structure matching dashboard_table.html expectations
    mock_context = {
        'holdings_by_category': {
            'Action': [
                {
                    'holding': {
                        'asset': {'ticker': 'AAPL', 'name': 'Apple Inc.'},
                        'quantity': 10
                    },
                    'current_price': 150.50,
                    'current_value': 1505.00,
                    'pnl': 500.00,
                    'pnl_percent': 33.33
                }
            ]
        }
    }
    
    try:
        t = get_template('portfolio/partials/dashboard_table.html')
        rendered = t.render(mock_context)
        print("Rendered Output:")
        print(rendered)
        
        # Check for literal braces
        if '{{' in rendered:
            print("\nFAIL: Found literal template tags in output!")
        else:
            print("\nSUCCESS: No literal template tags found.")
            
    except Exception as e:
        print(f"Error rendering template: {e}")

if __name__ == "__main__":
    test_render()
