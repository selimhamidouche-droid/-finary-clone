from django.core.management.base import BaseCommand
from portfolio.models import Asset, AssetCategory

class Command(BaseCommand):
    help = 'Seeds the database with common assets'

    def handle(self, *args, **kwargs):
        common_assets = [
            {'ticker': 'AAPL', 'name': 'Apple Inc.', 'category': AssetCategory.STOCKS, 'price': 185.00},
            {'ticker': 'MSFT', 'name': 'Microsoft Corporation', 'category': AssetCategory.STOCKS, 'price': 420.00},
            {'ticker': 'GOOGL', 'name': 'Alphabet Inc.', 'category': AssetCategory.STOCKS, 'price': 175.00},
            {'ticker': 'AMZN', 'name': 'Amazon.com Inc.', 'category': AssetCategory.STOCKS, 'price': 180.00},
            {'ticker': 'TSLA', 'name': 'Tesla Inc.', 'category': AssetCategory.STOCKS, 'price': 170.00},
            {'ticker': 'NVDA', 'name': 'NVIDIA Corporation', 'category': AssetCategory.STOCKS, 'price': 900.00},
            {'ticker': 'LVMUY', 'name': 'LVMH Moët Hennessy', 'category': AssetCategory.STOCKS, 'price': 160.00},
            {'ticker': 'BTC-USD', 'name': 'Bitcoin', 'category': AssetCategory.CRYPTO, 'price': 65000.00},
            {'ticker': 'ETH-USD', 'name': 'Ethereum', 'category': AssetCategory.CRYPTO, 'price': 3500.00},
            {'ticker': 'SOL-USD', 'name': 'Solana', 'category': AssetCategory.CRYPTO, 'price': 145.00},
        ]

        self.stdout.write('Creating assets with initial prices...')

        for item in common_assets:
            ticker = item['ticker']
            price = item['price']

            obj, created = Asset.objects.update_or_create(
                ticker=ticker,
                defaults={
                    'name': item['name'],
                    'category': item['category'],
                    'current_price': price
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created {ticker}'))
            else:
                self.stdout.write(f'Updated {ticker}')

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {len(common_assets)} assets.'))

