"""
JARVIS Crypto Watch Module
Cardano price tracker

Author: Rashi AI
Built for: Akshay
"""

import requests
from typing import Dict, Any


def get_ada_price(currency: str = 'inr') -> Dict[str, Any]:
    """
    Get Cardano (ADA) price
    
    Args:
        currency: Currency (inr, usd, eur)
        
    Returns:
        Dict with price info
    """
    try:
        # CoinGecko API (free, no key needed)
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': 'cardano',
            'vs_currencies': currency
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        price = data['cardano'][currency]
        
        return {
            'success': True,
            'coin': 'Cardano',
            'symbol': 'ADA',
            'price': price,
            'currency': currency.upper(),
            'price_formatted': f'₹{price}' if currency == 'inr' else f'${price}'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def get_crypto_prices(coins: list = None, currency: str = 'inr') -> Dict[str, Any]:
    """Get multiple crypto prices"""
    if coins is None:
        coins = ['cardano', 'bitcoin', 'ethereum']
        
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': ','.join(coins),
            'vs_currencies': currency
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        results = {}
        for coin in coins:
            if coin in data:
                price = data[coin][currency]
                results[coin] = {
                    'price': price,
                    'currency': currency.upper(),
                    'formatted': f'₹{price}' if currency == 'inr' else f'${price}'
                }
                
        return {
            'success': True,
            'prices': results
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
