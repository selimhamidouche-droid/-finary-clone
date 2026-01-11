from django.shortcuts import render
from django.db.models import Sum, F
from django.contrib.auth.decorators import login_required
from .models import Portfolio, Holding, AssetCategory, PortfolioHistory, Asset, Transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from django.utils import timezone
from .forms import PortfolioForm, HoldingForm
from django.shortcuts import render, redirect, get_object_or_404
from .services import search_assets_online, create_asset_from_ticker
from django.contrib import messages
import datetime

def landing_page(request):
    # if request.user.is_authenticated:
    #     return redirect('portfolio:dashboard')
    return render(request, 'landing.html')

@login_required
def dashboard(request):
    user_portfolios = Portfolio.objects.filter(user=request.user)
    
    # Simple aggregation for all user portfolios
    holdings = Holding.objects.filter(portfolio__in=user_portfolios).select_related('asset')
    
    # Simple aggregation for all user portfolios
    holdings = Holding.objects.filter(portfolio__in=user_portfolios).select_related('asset')
    
    # Calculate Total Net Worth
    total_net_worth = 0
    total_invested = 0
    
    # Organize holdings by category
    holdings_by_category = {cat: [] for cat, _ in AssetCategory.choices}
    
    for holding in holdings:
        val = holding.current_value
        invested = holding.quantity * holding.average_buy_price
        
        total_net_worth += val
        total_invested += invested
        
        # Calculate current price safely
        current_price = val / holding.quantity if holding.quantity else 0

        item = {
            'holding': holding,
            'current_value': val,
            'current_price': current_price,
            'pnl': val - invested,
            'pnl_percent': ((val - invested) / invested * 100) if invested else 0
        }
        holdings_by_category[holding.asset.category].append(item)
        
    # Remove empty categories and prepare chart data
    final_holdings_by_category = {}
    allocation_labels = []
    allocation_data = []

    for cat, items in holdings_by_category.items():
        if items:
            final_holdings_by_category[cat] = items
            # Use the display label for the category if available, otherwise code
            # We can find the label from AssetCategory.choices
            label = dict(AssetCategory.choices).get(cat, cat)
            allocation_labels.append(label)
            allocation_data.append(len(items))
            
    holdings_by_category = final_holdings_by_category
    
    # Calculate Daily Variation
    yesterday = timezone.localdate() - datetime.timedelta(days=1)
    
    # History for Yesterday (for variation)
    last_history = PortfolioHistory.objects.filter(portfolio__in=user_portfolios, date=yesterday).aggregate(Sum('total_value'))
    last_total_value = last_history['total_value__sum'] or 0
    
    if last_total_value:
        daily_variation = total_net_worth - last_total_value
        daily_variation_percent = (daily_variation / last_total_value) * 100
    else:
        daily_variation = 0
        daily_variation_percent = 0

    # Chart Data Preparation
    # We want a consolidated history of all portfolios.
    # Group by date and sum total_value.
    
    # Fetch all history for these portfolios, ordered by date
    history_qs = PortfolioHistory.objects.filter(portfolio__in=user_portfolios).order_by('date')
    
    # Aggregate by date in Python (simpler for now than advanced ORM grouping if not huge data)
    history_map = {}
    for h in history_qs:
        d_str = h.date.strftime('%d %b') # e.g. "04 Jan"
        history_map[d_str] = history_map.get(d_str, 0) + float(h.total_value)
        
    # Also add TODAY's value if not present (snapshot runs at night, real-time is updated)
    today_str = timezone.localdate().strftime('%d %b')
    if today_str not in history_map:
         history_map[today_str] = float(total_net_worth)
    
    # Sort keys by date? The map iteration order depends on insertion in Python 3.7+,
    # but let's be safe. We need proper sorting.
    # Re-sort based on original date objects would be better, but MVP:
    # Let's rely on the QS ordering.
    
    # Better approach:
    dates_labels = []
    values_data = []
    
    # Get distinct dates from DB
    distinct_dates = PortfolioHistory.objects.filter(portfolio__in=user_portfolios).values_list('date', flat=True).distinct().order_by('date')
    
    for d in distinct_dates:
        # Sum for this date
        day_sum = PortfolioHistory.objects.filter(portfolio__in=user_portfolios, date=d).aggregate(Sum('total_value'))['total_value__sum'] or 0
        dates_labels.append(d.strftime('%Y-%m-%d')) # ISO format for JS parsing or just simplified
        values_data.append(float(day_sum))
        
    # Append today current real-time value
    today_date = timezone.localdate()
    if not distinct_dates.filter(date=today_date).exists():
        dates_labels.append(today_date.strftime('%Y-%m-%d'))
        values_data.append(float(total_net_worth))

    context = {
        'total_net_worth': total_net_worth,
        'daily_variation': daily_variation,
        'daily_variation_percent': daily_variation_percent,
        'holdings_by_category': holdings_by_category,
        'chart_labels': dates_labels,
        'chart_data': values_data,
        'AssetCategory': AssetCategory,
        'allocation_labels': allocation_labels,
        'allocation_data': allocation_data,
    }
    
    if request.htmx:
        return render(request, 'portfolio/partials/dashboard_table.html', context)
        
    return render(request, 'portfolio/dashboard.html', context)

@login_required
def portfolio_list(request):
    portfolios = Portfolio.objects.filter(user=request.user)
    
    # Calculate value for each portfolio
    for portfolio in portfolios:
        total = 0
        holdings = portfolio.holdings.all()
        for h in holdings:
            total += h.current_value
        portfolio.total_value = total
        
    return render(request, 'portfolio/portfolio_list.html', {'portfolios': portfolios})

@login_required
def portfolio_create(request):
    if request.method == 'POST':
        form = PortfolioForm(request.POST)
        if form.is_valid():
            portfolio = form.save(commit=False)
            portfolio.user = request.user
            portfolio.save()
            return redirect('portfolio:portfolio_list')
    else:
        form = PortfolioForm()
    return render(request, 'portfolio/portfolio_form.html', {'form': form, 'action': 'Créer'})

@login_required
def portfolio_delete(request, pk):
    portfolio = get_object_or_404(Portfolio, pk=pk, user=request.user)
    if request.method == 'POST':
        portfolio.delete()
        return redirect('portfolio:portfolio_list')
    return render(request, 'portfolio/portfolio_confirm_delete.html', {'portfolio': portfolio})



@login_required
def portfolio_detail(request, pk):
    portfolio = get_object_or_404(Portfolio, pk=pk, user=request.user)
    
    # Calculate totals
    holdings = portfolio.holdings.all().select_related('asset')
    total_value = 0
    total_invested = 0
    
    for h in holdings:
        total_value += h.current_value
        total_invested += h.quantity * h.average_buy_price
        
    portfolio.total_value = total_value
    portfolio.pnl = total_value - total_invested
    portfolio.pnl_percent = (portfolio.pnl / total_invested * 100) if total_invested else 0
    
    return render(request, 'portfolio/portfolio_detail.html', {
        'portfolio': portfolio, 
        'holdings': holdings
    })

@login_required
def asset_detail(request, portfolio_id, asset_id):
    portfolio = get_object_or_404(Portfolio, pk=portfolio_id, user=request.user)
    asset = get_object_or_404(Asset, pk=asset_id)
    
    # Get the specific holding for this asset in this portfolio
    holding = get_object_or_404(Holding, portfolio=portfolio, asset=asset)
    
    # Get transactions related to this asset (filtering by string match on ticker roughly for now, 
    # since Transaction model is generic. In a real app we'd link Transaction to Asset FK).
    # MVP: Just show all user transactions for now or filter by description containing ticker
    transactions = Transaction.objects.filter(
        user=request.user, 
        description__icontains=asset.ticker
    ).order_by('-date')
    
    return render(request, 'portfolio/asset_detail.html', {
        'portfolio': portfolio,
        'asset': asset,
        'holding': holding,
        'transactions': transactions
    })

@login_required
def holding_create(request, portfolio_id):
    portfolio = get_object_or_404(Portfolio, pk=portfolio_id, user=request.user)
    if request.method == 'POST':
        form = HoldingForm(request.POST)
        if form.is_valid():
            new_holding = form.save(commit=False)
            asset = new_holding.asset
            quantity = new_holding.quantity
            price = new_holding.average_buy_price
            
            # Check for existing holding
            existing_holding = Holding.objects.filter(portfolio=portfolio, asset=asset).first()
            
            if existing_holding:
                # Calculate Weighted Average Price (Prix Moyen Pondéré)
                total_current_cost = existing_holding.quantity * existing_holding.average_buy_price
                total_new_cost = quantity * price
                new_total_quantity = existing_holding.quantity + quantity
                
                if new_total_quantity > 0:
                    weighted_price = (total_current_cost + total_new_cost) / new_total_quantity
                else:
                    weighted_price = 0
                    
                existing_holding.quantity = new_total_quantity
                existing_holding.average_buy_price = weighted_price
                existing_holding.save()
            else:
                new_holding.portfolio = portfolio
                new_holding.save()
                
            # Create Transaction Record
            Transaction.objects.create(
                user=request.user,
                amount=quantity * price,
                type=Transaction.Type.EXPENSE, # Keeping it simple for now, ideally 'BUY'
                category='Investment',
                description=f"Achat {asset.ticker} ({quantity} @ {price})",
                date=timezone.now().date(),
                source=Transaction.Source.MANUAL
            )
            
            return redirect('portfolio:portfolio_detail', pk=portfolio.pk)
    else:
        # Pre-select asset if passed in query params
        initial = {}
        asset_id = request.GET.get('asset')
        if asset_id:
            initial['asset'] = asset_id
        form = HoldingForm(initial=initial)
        
    return render(request, 'portfolio/holding_form.html', {'form': form, 'portfolio': portfolio})

@login_required
def holding_delete(request, pk):
    holding = get_object_or_404(Holding, pk=pk, portfolio__user=request.user)
    portfolio_pk = holding.portfolio.pk
    if request.method == 'POST':
        holding.delete()
        return redirect('portfolio:portfolio_detail', pk=portfolio_pk)
    return render(request, 'portfolio/holding_confirm_delete.html', {'holding': holding})

@login_required
def asset_list(request):
    from .services import fetch_market_data
    
    # Fetch user's saved assets
    my_assets = Asset.objects.all().order_by('category', 'name')
    
    # Fetch market overview data
    market_data = fetch_market_data()
    
    # Get active tab from query params
    active_tab = request.GET.get('tab', 'indices')
    
    context = {
        'assets': my_assets,
        'market_data': market_data,
        'active_tab': active_tab,
    }
    return render(request, 'portfolio/asset_list.html', context)

@login_required
def asset_search(request):
    query = request.GET.get('q', '')
    results = []
    if query:
        results = search_assets_online(query)
    
    if request.htmx:
        return render(request, 'portfolio/partials/asset_search_results.html', {'results': results, 'query': query})
        
    return render(request, 'portfolio/asset_search.html', {'results': results, 'query': query})

@login_required
def asset_add(request):
    ticker = request.POST.get('ticker')
    if ticker:
        asset = create_asset_from_ticker(ticker)
        if asset:
            messages.success(request, f"Actif {asset.name} ajouté avec succès.")
        else:
            messages.error(request, f"Impossible d'ajouter l'actif {ticker}.")
            
    return redirect('portfolio:asset_list')

@login_required
def insights(request):
    # Fetch all holdings for the user
    portfolios = Portfolio.objects.filter(user=request.user)
    holdings = Holding.objects.filter(portfolio__in=portfolios).select_related('asset')

    # 1. Total Wealth
    total_wealth = sum(h.current_value for h in holdings)
    
    # 2. Allocation by Category
    allocation = {}
    for h in holdings:
        cat = h.asset.get_category_display()
        allocation[cat] = allocation.get(cat, 0) + float(h.current_value)

    # 3. Diversification Score (0-100)
    # Simple logic: 100 - (Weight of largest single asset * 100)
    # If 0 assets, score is 0.
    if total_wealth > 0:
        asset_values = {}
        for h in holdings:
            asset_values[h.asset.ticker] = asset_values.get(h.asset.ticker, 0) + float(h.current_value)
        
        largest_asset_value = max(asset_values.values()) if asset_values else 0
        largest_weight = largest_asset_value / float(total_wealth)
        diversification_score = int(100 - (largest_weight * 100))
        # Cap score for edge cases (e.g. only 1 asset = score 0)
        diversification_score = max(0, min(100, diversification_score))
    else:
        diversification_score = 0

    # 4. Risk Radar Data (Mocked Logic based on real weights)
    # We estimate risk factors based on category weights
    crypto_weight = allocation.get('Crypto', 0) / float(total_wealth) if total_wealth else 0
    stocks_weight = allocation.get('Actions', 0) / float(total_wealth) if total_wealth else 0
    
    # Volatility: High if loads of crypto
    volatility_score = min(100, int((crypto_weight * 100) + (stocks_weight * 40)))
    
    # 5. Projected Dividends (Mock: 3% yield on Stocks)
    projected_dividends = allocation.get('Actions', 0) * 0.03

    context = {
        'total_wealth': total_wealth,
        'allocation': allocation,
        'diversification_score': diversification_score,
        'volatility_score': volatility_score,
        'projected_dividends': projected_dividends,
        'holdings_count': holdings.count(),
        
        # Risk Radar Chart Data
        'risk_labels': ['Volatilité', 'Géographie', 'Secteur', 'Liquidité', 'Devise'],
        'risk_data': [volatility_score, 50, 60, 80, 70], # Mocked simplified
    }
    
    return render(request, 'portfolio/insights.html', context)

@login_required
def transactions(request):
    transactions = Transaction.objects.filter(user=request.user)
    return render(request, 'portfolio/transactions.html', {'transactions': transactions})

@login_required
def transaction_create(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        type = request.POST.get('type')
        category = request.POST.get('category')
        description = request.POST.get('description')
        date = request.POST.get('date') or timezone.now().date()
        
        Transaction.objects.create(
            user=request.user,
            amount=amount,
            type=type,
            category=category,
            description=description,
            date=date,
            source=Transaction.Source.MANUAL
        )
        return redirect('portfolio:transactions')
    return redirect('portfolio:transactions')

@csrf_exempt
@require_POST
def webhook_transaction(request):
    try:
        data = json.loads(request.body)
        
        # Simple security check (removed for MVP based on user request)
        # if data.get('secret') != 'my-secret-key-123': 
        #    return JsonResponse({'error': 'Unauthorized'}, status=403)
            
        # Extract data (Simplified for Apple Shortcuts / Automation)
        amount = data.get('montant')
        merchant = data.get('commercant')
        card = data.get('card')
        date_str = data.get('date')

        # Fallback user for demo
        from django.contrib.auth.models import User
        user = User.objects.first()
        
        # Build description from Merchant + Card
        description = merchant if merchant else "Transaction"
        if card:
            description += f" ({card})"
            
        # Parse date if provided, else use today
        date = timezone.now().date()
        if date_str:
            try:
                # Handle simplified date formats if needed, or standard ISO
                # For now assume ISO YYYY-MM-DD or similar
                if 'T' in date_str:
                    date_str = date_str.split('T')[0]
                date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass # Fallback to today on error

        Transaction.objects.create(
            user=user,
            amount=amount,
            type='EXPENSE', # Default to Expense for this simplified endpoint
            category='Card Payment', # Default category
            description=description,
            date=date,
            source=Transaction.Source.WEBHOOK
        )
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def goals(request):
    return render(request, 'portfolio/goals.html')

@login_required
def settings(request):
    return render(request, 'portfolio/settings.html')

@login_required
def market_asset_detail(request, ticker):
    from .services import fetch_asset_details
    import json
    
    asset = fetch_asset_details(ticker)
    
    context = {
        'asset': asset,
        'chart_labels': json.dumps(asset.get('chart_labels', [])),
        'chart_data': json.dumps(asset.get('chart_data', [])),
    }
    return render(request, 'portfolio/market_asset_detail.html', context)
