from django.urls import path
from . import views

app_name = 'portfolio'

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('portfolios/', views.portfolio_list, name='portfolio_list'),
    path('portfolios/add/', views.portfolio_create, name='portfolio_create'),
    path('portfolios/<int:pk>/delete/', views.portfolio_delete, name='portfolio_delete'),
    path('portfolios/<int:pk>/', views.portfolio_detail, name='portfolio_detail'),
    path('portfolios/<int:portfolio_id>/add_holding/', views.holding_create, name='holding_create'),
    path('holdings/<int:pk>/delete/', views.holding_delete, name='holding_delete'),
    path('holdings/<int:pk>/delete/', views.holding_delete, name='holding_delete'),
    path('assets/', views.asset_list, name='asset_list'),
    path('assets/search/', views.asset_search, name='asset_search'),
    path('asset/add/', views.asset_add, name='asset_add'),
    path('insights/', views.insights, name='insights'),
    path('transactions/', views.transactions, name='transactions'),
    path('transactions/create/', views.transaction_create, name='transaction_create'),
    path('api/webhook/transaction/', views.webhook_transaction, name='webhook_transaction'),
    path('goals/', views.goals, name='goals'),
    path('settings/', views.settings, name='settings'),
]
