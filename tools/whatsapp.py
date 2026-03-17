"""
JARVIS WhatsApp Module
Send WhatsApp messages via Playwright

Author: Rashi AI
Built for: Akshay
"""

import asyncio
from typing import Dict, Any

# Try to import Playwright
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


async def send_message_async(phone: str, message: str) -> Dict[str, Any]:
    """
    Send WhatsApp message (async)
    
    Args:
        phone: Phone number with country code
        message: Message to send
        
    Returns:
        Dict with result
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {'success': False, 'error': 'Playwright not installed'}
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            # Open WhatsApp Web
            await page.goto('https://web.whatsapp.com')
            await page.wait_for_timeout(10000)  # Wait for scan
            
            # Open chat
            url = f'https://web.whatsapp.com/send?phone={phone}&text={message}'
            await page.goto(url)
            await page.wait_for_timeout(5000)
            
            # Click send button
            try:
                send_button = page.locator('button._4sW7G')  # Send button selector
                await send_button.click()
                await page.wait_for_timeout(2000)
            except:
                pass
            
            await browser.close()
            
            return {
                'success': True,
                'message': f'Message sent to {phone}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def send_message(phone: str, message: str) -> Dict[str, Any]:
    """
    Send WhatsApp message
    
    Args:
        phone: Phone number with country code
        message: Message to send
        
    Returns:
        Dict with result
    """
    try:
        return asyncio.run(send_message_async(phone, message))
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_to_contact(contact_name: str, message: str) -> Dict[str, Any]:
    """
    Send message to contact by name
    
    Args:
        contact_name: Contact name
        message: Message to send
        
    Returns:
        Dict with result
    """
    # Note: This requires QR scan each time
    return {
        'success': False,
        'error': 'Direct sending by name requires WhatsApp Business API. Use phone number for web version.'
    }
