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
    # Get total value from yesterday (or last available history)
    yesterday = timezone.localdate() - datetime.timedelta(days=1)
    
    # We sum history of all portfolios for yesterday
    # Note: This is an approximation if portfolios changed.
    last_history = PortfolioHistory.objects.filter(portfolio__in=user_portfolios, date=yesterday).aggregate(Sum('total_value'))
    last_total_value = last_history['total_value__sum'] or 0
    
    if last_total_value:
        daily_variation = total_net_worth - last_total_value
        daily_variation_percent = (daily_variation / last_total_value) * 100
    else:
        # If no history, maybe compare to invested? No, just 0.
        daily_variation = 0
        daily_variation_percent = 0

    context = {
        'total_net_worth': total_net_worth,
        'daily_variation': daily_variation,
        'daily_variation_percent': daily_variation_percent,
        'holdings_by_category': holdings_by_category,
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
def holding_create(request, portfolio_id):
    portfolio = get_object_or_404(Portfolio, pk=portfolio_id, user=request.user)
    if request.method == 'POST':
        form = HoldingForm(request.POST)
        if form.is_valid():
            holding = form.save(commit=False)
            holding.portfolio = portfolio
            holding.save()
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
    assets = Asset.objects.all().order_by('category', 'name')
    return render(request, 'portfolio/asset_list.html', {'assets': assets})

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
    return render(request, 'portfolio/insights.html')

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
        
        # Simple security check (replace with better auth in production)
        if data.get('secret') != 'my-secret-key-123': # TODO: Move to env var
            return JsonResponse({'error': 'Unauthorized'}, status=403)
            
        # Extract data (Simplified for Apple Shortcuts / Automation)
        amount = data.get('amount')
        merchant = data.get('merchant')
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

