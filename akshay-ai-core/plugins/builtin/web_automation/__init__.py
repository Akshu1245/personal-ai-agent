"""
============================================================
AKSHAY AI CORE — Web Automation Plugin
============================================================
Browser automation using Playwright for web scraping,
form filling, and automated testing.
============================================================
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from plugins.base import BuiltinPlugin, PluginMetadata, PluginConfig
from core.utils.logger import get_logger

logger = get_logger("plugin.web_automation")


class WebAutomationPlugin(BuiltinPlugin):
    """
    Web automation plugin using Playwright.
    
    Commands:
    - navigate: Navigate to a URL
    - screenshot: Take a screenshot
    - click: Click an element
    - fill: Fill a form field
    - scrape: Extract content from page
    - execute_script: Run JavaScript
    """
    
    metadata = PluginMetadata(
        name="web_automation",
        version="1.0.0",
        description="Browser automation for web scraping and testing",
        author="AKSHAY AI CORE",
        tags=["web", "automation", "scraping", "browser"],
    )
    
    config = PluginConfig(
        enabled=True,
        sandboxed=True,
        max_execution_time=300,
        permissions=["network:external", "file:write"],
        settings={
            "headless": True,
            "browser": "chromium",
            "timeout": 30000,
        },
    )
    
    def __init__(self):
        super().__init__()
        self._browser = None
        self._context = None
        self._page = None
    
    async def on_load(self) -> None:
        """Initialize Playwright browser."""
        self.register_command("navigate", self._cmd_navigate, "Navigate to a URL")
        self.register_command("screenshot", self._cmd_screenshot, "Take a screenshot")
        self.register_command("click", self._cmd_click, "Click an element")
        self.register_command("fill", self._cmd_fill, "Fill a form field")
        self.register_command("scrape", self._cmd_scrape, "Extract content from page")
        self.register_command("execute_script", self._cmd_execute_script, "Run JavaScript")
        
        logger.info("Web automation plugin loaded")
    
    async def on_unload(self) -> None:
        """Cleanup browser resources."""
        await self._close_browser()
    
    async def execute(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a web automation command."""
        return await self.dispatch_command(command, params)
    
    async def _ensure_browser(self) -> None:
        """Ensure browser is initialized."""
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright
                
                playwright = await async_playwright().start()
                
                browser_type = self.config.settings.get("browser", "chromium")
                browser_launcher = getattr(playwright, browser_type)
                
                self._browser = await browser_launcher.launch(
                    headless=self.config.settings.get("headless", True),
                )
                self._context = await self._browser.new_context()
                self._page = await self._context.new_page()
                
                # Set default timeout
                self._page.set_default_timeout(
                    self.config.settings.get("timeout", 30000)
                )
                
            except ImportError:
                raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install")
    
    async def _close_browser(self) -> None:
        """Close browser and cleanup."""
        if self._page:
            await self._page.close()
            self._page = None
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
    
    async def _cmd_navigate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Navigate to a URL."""
        url = params.get("url")
        if not url:
            return {"status": "error", "error": "URL required"}
        
        await self._ensure_browser()
        
        response = await self._page.goto(url)
        
        return {
            "status": "success",
            "url": self._page.url,
            "title": await self._page.title(),
            "response_status": response.status if response else None,
        }
    
    async def _cmd_screenshot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Take a screenshot."""
        await self._ensure_browser()
        
        path = params.get("path", f"screenshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png")
        full_page = params.get("full_page", False)
        
        await self._page.screenshot(path=path, full_page=full_page)
        
        return {
            "status": "success",
            "path": path,
            "url": self._page.url,
        }
    
    async def _cmd_click(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Click an element."""
        selector = params.get("selector")
        if not selector:
            return {"status": "error", "error": "Selector required"}
        
        await self._ensure_browser()
        
        await self._page.click(selector)
        
        return {"status": "success", "selector": selector}
    
    async def _cmd_fill(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fill a form field."""
        selector = params.get("selector")
        value = params.get("value", "")
        
        if not selector:
            return {"status": "error", "error": "Selector required"}
        
        await self._ensure_browser()
        
        await self._page.fill(selector, value)
        
        return {"status": "success", "selector": selector, "filled": True}
    
    async def _cmd_scrape(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract content from page."""
        await self._ensure_browser()
        
        selector = params.get("selector")
        attribute = params.get("attribute")
        
        if selector:
            elements = await self._page.query_selector_all(selector)
            
            if attribute:
                data = [await el.get_attribute(attribute) for el in elements]
            else:
                data = [await el.text_content() for el in elements]
        else:
            # Get full page content
            data = await self._page.content()
        
        return {
            "status": "success",
            "data": data,
            "url": self._page.url,
        }
    
    async def _cmd_execute_script(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute JavaScript on the page."""
        script = params.get("script")
        if not script:
            return {"status": "error", "error": "Script required"}
        
        await self._ensure_browser()
        
        result = await self._page.evaluate(script)
        
        return {
            "status": "success",
            "result": result,
        }
