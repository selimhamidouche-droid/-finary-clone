import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from portfolio.models import Portfolio, PortfolioHistory

class Command(BaseCommand):
    help = 'Populates 30 days of fake history for all portfolios'

    def handle(self, *args, **options):
        portfolios = Portfolio.objects.all()
        
        if not portfolios.exists():
            self.stdout.write(self.style.WARNING("No portfolios found. Create a portfolio first."))
            return

        today = timezone.now().date()
        
        for portfolio in portfolios:
            self.stdout.write(f"Generating history for {portfolio.name}...")
            
            # Calculate current total value
            current_total = sum(h.current_value for h in portfolio.holdings.all())
            current_invested = sum(h.quantity * h.average_buy_price for h in portfolio.holdings.all())
            
            # Generate 30 days of history
            for i in range(30, 0, -1):
                date = today - timedelta(days=i)
                
                # Random variation +/- 5% per day relative to current value
                # This treats history as if it fluctuated to reach today's value
                variation = random.uniform(0.95, 1.05)
                # We simply apply a random factor to the current value to simulate past values
                # To make it look more realistic, we should probably walk back from today
                # But simple random deviation from current is enough for MVP visual
                
                # Let's make it a walk: history_value = current * random_factor
                # To distinguish days, let's add a trend.
                # Assume market was lower 30 days ago (bull run)
                trend_factor = 1 - (i * 0.005) # 0.5% growth per day roughly
                
                daily_value = float(current_total) * trend_factor * random.uniform(0.98, 1.02)
                daily_invested = float(current_invested) # Assume invested didn't change (no buys/sells)
                
                PortfolioHistory.objects.update_or_create(
                    portfolio=portfolio,
                    date=date,
                    defaults={
                        'total_value': daily_value,
                        'invested_value': daily_invested
                    }
                )
                
        self.stdout.write(self.style.SUCCESS("Successfully populated history for all portfolios"))
