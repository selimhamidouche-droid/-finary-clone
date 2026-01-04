from django.contrib import admin
from .models import Asset, Portfolio, Holding, PortfolioHistory

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'name', 'category', 'current_price', 'last_updated')
    search_fields = ('ticker', 'name')
    list_filter = ('category',)

class HoldingInline(admin.TabularInline):
    model = Holding
    extra = 1

@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'currency')
    search_fields = ('name', 'user__username')
    inlines = [HoldingInline]

@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ('portfolio', 'asset', 'quantity', 'current_value', 'source')
    list_filter = ('source', 'portfolio')
    search_fields = ('asset__ticker', 'portfolio__name')

@admin.register(PortfolioHistory)
class PortfolioHistoryAdmin(admin.ModelAdmin):
    list_display = ('portfolio', 'date', 'total_value', 'invested_value')
    list_filter = ('portfolio', 'date')
    date_hierarchy = 'date'
