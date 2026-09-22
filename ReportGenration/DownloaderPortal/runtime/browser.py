from __future__ import annotations

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright


class BrowserManager:
    def __init__(self, profile_dir: Path):
        self.profile_dir = profile_dir
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.playwright = None
        self.context = None
        self.discovery_page = None

    async def start(self):
        # Reuse the already-running persistent context. A persistent
        # Chromium profile can have only one owner at a time.
        if self.context is not None:
            try:
                if not self.context.is_closed():
                    return self.context
            except Exception:
                pass

        if self.playwright is None:
            self.playwright = await async_playwright().start()

        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=False,
            accept_downloads=True,
        )
        return self.context

    async def stop(self):
        self.discovery_page = None
        if self.context:
            await self.context.close()
            self.context = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def new_page(self):
        if not self.context:
            await self.start()
        return await self.context.new_page()

    async def open_discovery_page(self, url: str):
        if not self.context:
            await self.start()

        if self.discovery_page is None:
            self.discovery_page = await self.context.new_page()
        else:
            try:
                if self.discovery_page.is_closed():
                    self.discovery_page = await self.context.new_page()
            except Exception:
                self.discovery_page = await self.context.new_page()

        await self.discovery_page.goto(url, wait_until="domcontentloaded", timeout=60000)
        return self.discovery_page
