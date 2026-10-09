import asyncio
import csv
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

from common import BASE, FIXTURES, OUTPUT


async def wait_ready(page):
    await page.wait_for_function("document.querySelector('#mainContent').getAttribute('aria-busy') === 'false' && !document.querySelector('#locationSelect').disabled")


async def main():
    snapshots = {row["DiaDiem"]["MaDiaDiem"]: row for row in json.loads((FIXTURES / "locations.json").read_text(encoding="utf-8"))}
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page = await context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(BASE, wait_until="domcontentloaded")
        await wait_ready(page)
        assert await page.locator("#locationSelect option").count() == 86
        await page.locator("#locationSearch").fill("cau giay")
        options = await page.locator("#locationSelect option").all_text_contents()
        assert any("Cầu Giấy" in text for text in options), options
        await page.locator("#locationSearch").fill("")
        await page.locator("#locationSelect").select_option("tphcm")
        await wait_ready(page)
        assert "Hồ Chí Minh" in await page.locator("#locationTitle").inner_text()
        assert "Hồ Chí Minh" in await page.locator("#reportTitle").inner_text()
        assert "Chưa có" in await page.locator("#noiseSourceNote").inner_text()
        async with page.expect_download() as download_info:
            await page.locator("#reportCsv").click()
        download = await download_info.value
        assert "tphcm" in download.suggested_filename
        text = Path(await download.path()).read_text(encoding="utf-8-sig")
        rows = list(csv.reader(io.StringIO(text)))
        assert len(rows[0]) == 17 and all(len(row) == 17 and row[1] == "tphcm" for row in rows[1:])
        await page.reload(wait_until="domcontentloaded")
        await wait_ready(page)
        assert await page.locator("#locationSelect").input_value() == "tphcm"
        await page.screenshot(path=str(OUTPUT / "locations-desktop.png"))
        await page.set_viewport_size({"width": 390, "height": 844})
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile horizontal overflow"
        await page.screenshot(path=str(OUTPUT / "locations-mobile.png"))
        await page.locator("#locationSelect").select_option("hue")
        await wait_ready(page)
        assert await page.locator("#reportOutput").is_hidden()
        assert "Huế" in await page.locator("#reportHistory").inner_text()
        await context.close()
        print("Live UI: 86 choices, unaccented search, city-specific reports/CSV, remembered selection and mobile layout OK.", flush=True)

        mock = await browser.new_context(viewport={"width": 1280, "height": 900})
        test = await mock.new_page()
        test.on("pageerror", lambda error: errors.append(str(error)))
        posts = []
        delayed = asyncio.Event()

        async def current(route):
            identifier = parse_qs(urlparse(route.request.url).query)["location"][0]
            if identifier == "hanoi":
                delayed.set()
                await asyncio.sleep(.8)
            result = json.loads(json.dumps(snapshots[identifier]))
            result["DuLieu"]["PM25"] = 111 if identifier == "hanoi" else 222
            try:
                await route.fulfill(json=result)
            except Exception:
                pass  # The old request is intentionally cancelled on selection change.

        async def reply(route):
            body = route.request.post_data_json
            posts.append(body)
            await asyncio.sleep(.5)
            await route.fulfill(json={"reply": "Trả lời cho " + body["location"], "truncated": False})

        await test.route("**/api/capnhat?**", current)
        await test.route("**/api/baocao?**", lambda route: route.fulfill(json=[]))
        await test.route("**/api/dulieu/lichsu?**", lambda route: route.fulfill(json=[]))
        await test.route("**/api/canhbao?**", lambda route: route.fulfill(json=[]))
        await test.route("**/api/chat", reply)
        await test.goto(BASE, wait_until="domcontentloaded")
        await delayed.wait()
        await test.wait_for_function("!document.querySelector('#locationSelect').disabled && document.querySelector('#locationSelect').options.length === 86")
        await test.locator("#locationSelect").select_option("tphcm")
        await wait_ready(test)
        await test.wait_for_timeout(900)
        assert await test.locator('[data-metric="pm25"] [data-role="value"]').inner_text() == "222.0"
        await test.locator("#chatInput").fill("Câu hỏi TP.HCM")
        await test.locator("#chatSend").click()
        await test.wait_for_function("document.querySelector('#locationSelect').disabled")
        await test.wait_for_function("!document.querySelector('#chatSend').disabled")
        assert posts[-1]["location"] == "tphcm" and posts[-1]["history"] == []
        await test.locator("#locationSelect").select_option("hanoi")
        await wait_ready(test)
        assert "Câu hỏi TP.HCM" not in await test.locator("#chatMessages").inner_text()
        await test.locator("#chatInput").fill("Câu hỏi Hà Nội")
        await test.locator("#chatSend").click()
        await test.wait_for_function("!document.querySelector('#chatSend').disabled")
        assert posts[-1]["location"] == "hanoi" and posts[-1]["history"] == []
        await test.locator("#locationSelect").select_option("tphcm")
        await wait_ready(test)
        assert "Câu hỏi TP.HCM" in await test.locator("#chatMessages").inner_text()
        assert "Câu hỏi Hà Nội" not in await test.locator("#chatMessages").inner_text()
        assert not errors, errors
        print("Async UI: stale responses ignored, selector held during replies, chat context/history isolated; no JavaScript errors.", flush=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
