"""No live requests. Check the conditions that previously hid missing records."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from scraper.accela_scraper import go_to_next_page, start_search, get_attachments_from_record
from playwright.async_api import TimeoutError as PlaywrightTimeout


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    @patch("scraper.accela_scraper.asyncio.sleep", new_callable=AsyncMock)
    async def test_cannot_silently_ignore_wrong_permit_type(self, sleep):
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.fill = AsyncMock()
        page.select_option = AsyncMock(side_effect=RuntimeError("missing option"))
        with self.assertRaisesRegex(RuntimeError, "unscoped search"):
            await start_search(page)

    @patch("scraper.accela_scraper.asyncio.sleep", new_callable=AsyncMock)
    async def test_stalled_next_page_is_not_the_last_page(self, sleep):
        locator = MagicMock()
        locator.first = locator
        locator.count = AsyncMock(return_value=1)
        locator.is_visible = AsyncMock(return_value=True)
        locator.text_content = AsyncMock(return_value="unchanged first record")
        locator.click = AsyncMock()
        page = MagicMock()
        page.locator.return_value = locator
        page.wait_for_load_state = AsyncMock()
        with self.assertRaisesRegex(RuntimeError, "did not advance"):
            await go_to_next_page(page, retries=1)
        locator.count = AsyncMock(return_value=0)
        self.assertFalse(await go_to_next_page(page, retries=1))

    async def test_timed_out_record_remains_retryable(self):
        page = MagicMock()
        page.goto = AsyncMock(side_effect=PlaywrightTimeout("timeout"))
        downloads, status = await get_attachments_from_record(page, None, "https://example.org", "permit")
        self.assertEqual(downloads, [])
        self.assertEqual(status, "failed")


if __name__ == "__main__":
    unittest.main()
