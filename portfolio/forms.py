from django import forms
from .models import Portfolio, Holding, Asset

class PortfolioForm(forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ['name', 'currency']
        labels = {
            'name': 'Nom du portefeuille',
            'currency': 'Devise',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
            'currency': forms.TextInput(attrs={'class': 'mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
        }

class HoldingForm(forms.ModelForm):
    class Meta:
        model = Holding
        fields = ['asset', 'quantity', 'average_buy_price', 'source']
        labels = {
            'asset': 'Actif',
            'quantity': 'Quantité',
            'average_buy_price': 'Prix Moyen d\'Achat',
            'source': 'Source',
        }
        widgets = {
            'asset': forms.Select(attrs={'class': 'mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
            'average_buy_price': forms.NumberInput(attrs={'class': 'mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
            'source': forms.Select(attrs={'class': 'mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'}),
        }
