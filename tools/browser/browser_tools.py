"""Stateful Playwright browser tools for FRIDAY."""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from langchain.tools import tool
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from core.runtime.permissions import get_workspace_root

_MAX_TEXT_CHARS = 40_000
_TIMEOUT_MS = 15_000

_playwright_var: ContextVar[Playwright | None] = ContextVar("friday_playwright", default=None)
browser_var: ContextVar[Browser | None] = ContextVar("friday_browser", default=None)
context_var: ContextVar[BrowserContext | None] = ContextVar("friday_browser_context", default=None)
page_var: ContextVar[Page | None] = ContextVar("friday_browser_page", default=None)


def _validate_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only absolute HTTP(S) URLs are supported.")
    return url.strip()


async def _page() -> Page:
    page = page_var.get()
    if page and not page.is_closed():
        return page
    playwright = _playwright_var.get()
    browser = browser_var.get()
    context = context_var.get()
    if not playwright or not browser or not context:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        _playwright_var.set(playwright)
        browser_var.set(browser)
        context_var.set(context)
    page = await context.new_page()
    page.set_default_timeout(_TIMEOUT_MS)
    page_var.set(page)
    return page


@tool("browser_navigate")
async def browser_navigate(url: str) -> dict[str, Any]:
    """Navigate the current FRIDAY browser session to a public webpage."""
    page = await _page()
    target = _validate_url(url)
    response = await page.goto(target, wait_until="domcontentloaded")
    return {"url": page.url, "title": await page.title(), "status": response.status if response else None}


@tool("browser_read_page")
async def browser_read_page() -> dict[str, Any]:
    """Extract bounded readable text from the current browser page."""
    page = await _page()
    text = await page.locator("body").inner_text()
    return {"url": page.url, "title": await page.title(), "text": " ".join(text.split())[:_MAX_TEXT_CHARS]}


@tool("browser_click")
async def browser_click(selector_or_description: str) -> dict[str, Any]:
    """Click an element by CSS selector, exact text, or role:name."""
    page = await _page()
    target = selector_or_description.strip()
    try:
        if target.startswith("text="):
            await page.get_by_text(target[5:], exact=True).click()
        elif target.startswith("role:"):
            spec = target[5:]
            role, _, name = spec.partition("/")
            if not role:
                raise ValueError("Role target must look like role:button/Submit")
            await page.get_by_role(role, name=name or None).click()
        else:
            await page.locator(target).click()
    except Exception as error:
        raise RuntimeError(f"Browser click failed for '{target}': {error}") from error
    return {"url": page.url, "title": await page.title()}


@tool("browser_type")
async def browser_type(text: str, selector: str | None = None) -> dict[str, Any]:
    """Type text into a deterministic CSS-selected input."""
    if not selector:
        raise ValueError("A CSS selector is required for browser.type to avoid ambiguous input targeting.")
    page = await _page()
    await page.locator(selector).fill(text)
    return {"url": page.url, "selector": selector, "characters": len(text)}


@tool("browser_screenshot")
async def browser_screenshot(full_page: bool = False) -> dict[str, Any]:
    """Capture the current browser page to the scoped workspace."""
    page = await _page()
    output_dir = get_workspace_root() / ".friday" / "browser"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "latest.png"
    await page.screenshot(path=str(path), full_page=full_page)
    return {"url": page.url, "path": str(path), "full_page": full_page}


@tool("browser_close")
async def browser_close() -> dict[str, str]:
    """Close the current browser session."""
    browser = browser_var.get()
    playwright = _playwright_var.get()
    if browser:
        await browser.close()
    if playwright:
        await playwright.stop()
    browser_var.set(None)
    context_var.set(None)
    page_var.set(None)
    _playwright_var.set(None)
    return {"status": "closed"}


BROWSER_LANGCHAIN_TOOLS = [browser_navigate, browser_read_page, browser_click, browser_type, browser_screenshot, browser_close]
