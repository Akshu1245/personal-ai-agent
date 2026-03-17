"""
JARVIS PDF/Article Summarizer Module
Summarize PDFs and articles using PyMuPDF + Groq

Author: Rashi AI
Built for: Akshay
"""

import requests
from pathlib import Path
from typing import Dict, Any

# Try to import PyMuPDF
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


def extract_text_from_pdf(file_path: str) -> Dict[str, Any]:
    """
    Extract text from PDF
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Dict with extracted text
    """
    if not PYMUPDF_AVAILABLE:
        return {'success': False, 'error': 'PyMuPDF not installed'}
    
    try:
        doc = fitz.open(file_path)
        text = ""
        
        for page in doc:
            text += page.get_text()
        
        doc.close()
        
        return {
            'success': True,
            'text': text,
            'pages': len(doc),
            'length': len(text)
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def summarize_pdf(file_path: str, max_length: int = 500) -> Dict[str, Any]:
    """
    Summarize a PDF document
    
    Args:
        file_path: Path to PDF
        max_length: Max summary length
        
    Returns:
        Dict with summary
    """
    # Extract text
    result = extract_text_from_pdf(file_path)
    if not result.get('success'):
        return result
    
    text = result['text']
    
    # For now, return first part as summary
    # Full implementation would use Groq to summarize
    summary = text[:max_length] + "..." if len(text) > max_length else text
    
    return {
        'success': True,
        'summary': summary,
        'full_text_length': len(text),
        'pages': result['pages']
    }


def extract_text_from_url(url: str) -> Dict[str, Any]:
    """
    Extract text from article URL
    
    Args:
        url: Article URL
        
    Returns:
        Dict with extracted text
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Simple HTML to text (would use BeautifulSoup in production)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove scripts and styles
        for script in soup(['script', 'style']):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return {
            'success': True,
            'text': text[:5000],  # Limit
            'url': url
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def summarize_article(url: str) -> Dict[str, Any]:
    """
    Summarize an article from URL
    
    Args:
        url: Article URL
        
    Returns:
        Dict with summary
    """
    result = extract_text_from_url(url)
    if not result.get('success'):
        return result
    
    text = result['text']
    
    # Return first part as summary
    summary = text[:500] + "..." if len(text) > 500 else text
    
    return {
        'success': True,
        'summary': summary,
        'full_length': len(text),
        'url': url,
        'note': 'Full AI summarization requires Groq API'
    }
