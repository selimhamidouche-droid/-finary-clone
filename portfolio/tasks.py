from celery import shared_task
from django.utils import timezone
from .models import Asset, Portfolio, PortfolioHistory
from .services import update_asset_prices
import logging

logger = logging.getLogger(__name__)

@shared_task
def update_all_asset_prices():
    """
    Updates prices for all assets in the database.
    Runs every 15 minutes.
    """
    assets = list(Asset.objects.all())
    if not assets:
        logger.info("No assets to update.")
        return
    
    logger.info(f"Updating prices for {len(assets)} assets...")
    update_asset_prices(assets)
    logger.info("Asset prices updated.")

@shared_task
def snapshot_daily_portfolio():
    """
    Snapshots the value of all portfolios.
    Runs daily at midnight.
    """
    today = timezone.localdate()
    logger.info(f"Taking portfolio snapshots for {today}")
    
    portfolios = Portfolio.objects.all()
    
    for portfolio in portfolios:
        try:
            total_value = 0
            invested_value = 0
            
            # Recalculate totals from holdings
            for holding in portfolio.holdings.all():
                # We assume Asset price is fresh enough (updated every 15m)
                total_value += holding.current_value
                invested_value += holding.quantity * holding.average_buy_price
            
            # Create or update history for today
            PortfolioHistory.objects.update_or_create(
                portfolio=portfolio,
                date=today,
                defaults={
                    'total_value': total_value,
                    'invested_value': invested_value
                }
            )
        except Exception as e:
            logger.error(f"Error snapshotting portfolio {portfolio.name}: {e}")
            
    logger.info("Portfolio snapshots completed.")
