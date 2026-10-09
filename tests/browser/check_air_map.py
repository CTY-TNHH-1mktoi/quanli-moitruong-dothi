import asyncio
import json
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

from common import BASE, FIXTURES, OUTPUT, no_measurement_writes


async def ready(page):
    await page.wait_for_function("document.querySelector('#mapAirStatus').textContent.includes('Nguồn lúc') && !document.querySelector('#locationSelect').disabled", timeout=45000)


def profile_script():
    return """() => {
      const canvas=document.querySelector('.air-quality-canvas');
      const context=canvas.getContext('2d');
      const bytes=context.getImageData(0,0,canvas.width,canvas.height).data;
      let painted=0;
      const colors=new Set();
      for(let i=0;i<bytes.length;i+=4) if(bytes[i+3]) { painted++; colors.add(`${bytes[i]},${bytes[i+1]},${bytes[i+2]}`); }
      return {painted, colors:colors.size, center:Array.from(context.getImageData(Math.floor(canvas.width/2),Math.floor(canvas.height/2),1,1).data)};
    }"""


async def main():
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='msedge', headless=True)
        context = await browser.new_context(viewport={'width': 1440, 'height': 1100})
        page = await context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        await no_measurement_writes(page)
        await page.goto(BASE, wait_until='domcontentloaded')
        await ready(page)
        profile = await page.evaluate(profile_script())
        assert profile['painted'] > 1000 and profile['colors'] > 10, profile
        assert 'Hà Nội' in await page.locator('#mapHeading').inner_text()
        assert await page.locator('#mapAirLegend li').count() == 6
        await page.locator('#locationMap').scroll_into_view_if_needed()
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(OUTPUT / 'air-map-desktop.png'))
        await page.locator('#locationMap').click(position={'x': 430, 'y': 240})
        assert 'US AQI ước tính' in await page.locator('.leaflet-popup-content').last.inner_text()
        await page.locator('.leaflet-popup-close-button').click()
        await page.locator('.leaflet-popup-content').wait_for(state='detached')
        await page.locator('#mapAirOpacity').fill('35')
        assert await page.locator('#mapAirOpacityValue').inner_text() == '35%'
        assert await page.locator('.air-quality-canvas').evaluate('(node)=>node.style.opacity') == '0.35'
        await page.locator('#mapAirOpacity').fill('68')
        await page.locator('#mapAirToggle').uncheck()
        assert await page.locator('.air-quality-canvas').count() == 0
        assert await page.locator('#mapAirLegend').is_hidden()
        assert await page.locator('#locationMap .map-pin').count() == 2
        await page.locator('#mapAirToggle').check()
        await ready(page)
        if await page.locator('#mapFullscreen').is_visible():
            await page.locator('#mapFullscreen').click()
            await page.wait_for_function('document.fullscreenElement !== null')
            await page.locator('#mapFullscreen').click()
            await page.wait_for_function('document.fullscreenElement === null')
        await page.locator('#locationSelect').select_option('tphcm')
        await ready(page)
        assert 'Hồ Chí Minh' in await page.locator('#mapHeading').inner_text()
        assert (await page.evaluate(profile_script()))['painted'] > 1000
        await page.set_viewport_size({'width': 390, 'height': 844})
        await page.locator('.location-map-card').scroll_into_view_if_needed()
        await ready(page)
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(OUTPUT / 'air-map-mobile.png'))
        await page.route('**/api/bando/khongkhi?**', lambda route: route.fulfill(status=502, json={'loi': 'Nguồn AQI đang tạm lỗi.'}))
        await page.locator('#locationSelect').select_option('hue')
        await page.locator('#mapAirRetry').wait_for(state='visible')
        assert (await page.evaluate(profile_script()))['painted'] == 0
        assert await page.locator('#locationMap .map-pin.environment').count() == 1
        await page.unroute('**/api/bando/khongkhi?**')
        await page.locator('#mapAirRetry').click()
        await ready(page)
        assert (await page.evaluate(profile_script()))['painted'] > 1000
        print({'live_render': profile, 'controls': 'opacity/toggle/fullscreen/popup OK', 'cities': 'Hanoi/TP.HCM/Hue', 'network_error_recovery': 'OK', 'mobile': 'no overflow'}, flush=True)
        await context.close()

        # A slow response for the previous city must never paint the new city.
        context = await browser.new_context(viewport={'width': 1280, 'height': 900})
        page = await context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        await no_measurement_writes(page)
        started = asyncio.Event()

        async def mocked_grid(route):
            identifier = parse_qs(urlparse(route.request.url).query)['location'][0]
            if identifier == 'hanoi':
                started.set()
                await asyncio.sleep(.8)
            data = json.loads((FIXTURES / f'aqi-{identifier}.json').read_text(encoding='utf-8'))
            data['AQI'] = [[50 if identifier == 'hanoi' else 200 for _ in data['KinhDo']] for _ in data['ViDo']]
            try:
                await route.fulfill(json=data)
            except Exception:
                pass

        await page.route('**/api/bando/khongkhi?**', mocked_grid)
        await page.goto(BASE, wait_until='domcontentloaded')
        await started.wait()
        await page.wait_for_function("!document.querySelector('#locationSelect').disabled")
        await page.locator('#locationSelect').select_option('tphcm')
        await ready(page)
        await page.wait_for_timeout(1000)
        assert (await page.evaluate(profile_script()))['center'] == [255, 0, 0, 255]
        assert not errors, errors
        print('Stale-response isolation passed; no JavaScript errors.', flush=True)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
