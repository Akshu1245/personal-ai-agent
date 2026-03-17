"""
JARVIS Web Search Module
DuckDuckGo/Google search

Author: Rashi AI
Built for: Akshay
"""

import requests
from typing import Dict, Any, List
from bs4 import BeautifulSoup


def search(query: str, num_results: int = 5) -> Dict[str, Any]:
    """
    Search the web using DuckDuckGo
    
    Args:
        query: Search query
        num_results: Number of results to return
        
    Returns:
        Dict with search results
    """
    try:
        # Use DuckDuckGo HTML
        url = "https://html.duckduckgo.com/html/"
        params = {'q': query}
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse results
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        for result in soup.select('.result')[:num_results]:
            title_elem = result.select_one('.result__title')
            snippet_elem = result.select_one('.result__snippet')
            link_elem = result.select_one('.result__url')
            
            if title_elem:
                results.append({
                    'title': title_elem.get_text(strip=True),
                    'snippet': snippet_elem.get_text(strip=True) if snippet_elem else '',
                    'url': link_elem.get_text(strip=True) if link_elem else ''
                })
                
        return {
            'success': True,
            'query': query,
            'count': len(results),
            'results': results
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def search_google(query: str, num_results: int = 5) -> Dict[str, Any]:
    """
    Search using Google (requires different approach due to blocking)
    
    Args:
        query: Search query
        num_results: Number of results
        
    Returns:
        Dict with search results
    """
    # For now, just use DuckDuckGo
    return search(query, num_results)


def scrape_page(url: str) -> Dict[str, Any]:
    """
    Scrape a webpage
    
    Args:
        url: URL to scrape
        
    Returns:
        Dict with page content
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove scripts and styles
        for script in soup(['script', 'style']):
            script.decompose()
            
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return {
            'success': True,
            'url': url,
            'title': soup.title.string if soup.title else '',
            'text': text[:5000],  # Limit text length
            'length': len(text)
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
