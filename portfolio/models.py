from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class AssetCategory(models.TextChoices):
    STOCKS = 'STOCKS', 'Actions'
    CRYPTO = 'CRYPTO', 'Crypto'
    FIAT = 'FIAT', 'Monnaie Fiat'
    REAL_ESTATE = 'REAL_ESTATE', 'Immobilier'

class ConnectionSource(models.TextChoices):
    MANUAL = 'MANUAL', 'Manuel'
    API = 'API', 'API'

class Asset(models.Model):
    ticker = models.CharField(max_length=20, unique=True, help_text="e.g. AAPL, BTC/USDT")
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=AssetCategory.choices)
    current_price = models.DecimalField(max_digits=20, decimal_places=10, default=0.0)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} ({self.ticker})"

class Portfolio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolios')
    name = models.CharField(max_length=100)
    currency = models.CharField(max_length=3, default="EUR")

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class Holding(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='holdings')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='holdings')
    quantity = models.DecimalField(max_digits=20, decimal_places=10, help_text="Supports crypto decimals")
    average_buy_price = models.DecimalField(max_digits=20, decimal_places=10, default=0.0)
    source = models.CharField(max_length=20, choices=ConnectionSource.choices, default=ConnectionSource.MANUAL)

    @property
    def current_value(self):
        return self.quantity * self.asset.current_price

    @property
    def invested_value(self):
        return self.quantity * self.average_buy_price

    @property
    def neg_invested(self):
        """Returns negative invested value for simple P&L addition in templates"""
        return -self.invested_value

    @property
    def pnl(self):
        return self.current_value - self.invested_value

    @property
    def pnl_percent(self):
        if self.invested_value > 0:
            return (self.pnl / self.invested_value) * 100
        return 0

    def __str__(self):
        return f"{self.quantity} {self.asset.ticker} in {self.portfolio.name}"

class PortfolioHistory(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='history')
    date = models.DateField()
    total_value = models.DecimalField(max_digits=20, decimal_places=2)
    invested_value = models.DecimalField(max_digits=20, decimal_places=2)

    class Meta:
        ordering = ['-date']
        unique_together = ['portfolio', 'date']

    def __str__(self):
        return f"{self.portfolio.name} - {self.date}: {self.total_value}"

class Transaction(models.Model):
    class Type(models.TextChoices):
        INCOME = 'INCOME', 'Revenu'
        EXPENSE = 'EXPENSE', 'Dépense'
        DEPOSIT = 'DEPOSIT', 'Dépôt'
        WITHDRAWAL = 'WITHDRAWAL', 'Retrait'

    class Source(models.TextChoices):
        MANUAL = 'MANUAL', 'Manuel'
        WEBHOOK = 'WEBHOOK', 'Automatisé (Webhook)'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.EXPENSE)
    category = models.CharField(max_length=50, help_text="Catégorie (ex: Alimentation, Salaire)")
    description = models.CharField(max_length=200, blank=True)
    date = models.DateField(default=timezone.now)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.type} - {self.amount} ({self.date})"
