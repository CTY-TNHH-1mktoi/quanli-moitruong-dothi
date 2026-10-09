import asyncio
import math
from urllib.parse import urlparse, parse_qs

from playwright.async_api import async_playwright

from common import BASE, OUTPUT, no_measurement_writes


async def ready(page):
    await page.wait_for_function("document.querySelector('#locationMap .map-pin.environment') && !document.querySelector('#locationSelect').disabled")


async def main():
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='msedge', headless=True)
        context = await browser.new_context(viewport={'width': 1440, 'height': 1100})
        page = await context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        tile_requests = []
        page.on('request', lambda request: tile_requests.append(request.url) if 'tile.openstreetmap.org/' in request.url else None)
        # Keep the location/catalogue and map live; avoid generating extra measurements or reports.
        await no_measurement_writes(page)
        await page.goto(BASE, wait_until='domcontentloaded')
        await ready(page)
        await page.locator('#mapAirToggle').uncheck()
        assert await page.locator('#locationMap .map-pin').count() == 2
        assert await page.locator('#mapNoiseLegend').is_visible()
        assert '21.02850, 105.85420' in await page.locator('#mapLocationLabel').inner_text()
        await page.locator('#locationMap .map-pin.environment').click()
        assert 'Hà Nội' in await page.locator('.leaflet-popup-content').inner_text()
        await page.locator('.leaflet-popup-close-button').click()
        await page.locator('.leaflet-popup-content').wait_for(state='detached')
        await page.locator('#locationMap .map-pin.noise').click()
        assert 'Cầu Giấy' in await page.locator('.leaflet-popup-content').inner_text()
        await page.locator('.leaflet-popup-close-button').click()
        await page.locator('.leaflet-popup-content').wait_for(state='detached')
        await page.locator('#locationSelect').select_option('tphcm')
        await ready(page)
        assert await page.locator('#locationMap .map-pin').count() == 1
        assert await page.locator('#mapNoiseLegend').is_hidden()
        assert '10.82302, 106.62965' in await page.locator('#mapLocationLabel').inner_text()
        href = await page.locator('#mapOpen').get_attribute('href')
        assert parse_qs(urlparse(href).query) == {'mlat': ['10.82302'], 'mlon': ['106.62965']}
        await page.wait_for_function("document.querySelectorAll('#locationMap img.leaflet-tile-loaded').length > 0", timeout=30000)
        await page.wait_for_timeout(1000)
        assert await page.locator('#mapRetry').is_hidden(), await page.locator('#mapStatus').inner_text()
        # The requested tile coordinates must cover the actual selected location.
        x = math.floor((106.62965 + 180) / 360 * 2**12)
        lat = math.radians(10.82302)
        y = math.floor((1 - math.asinh(math.tan(lat)) / math.pi) / 2 * 2**12)
        assert any(f'/12/{x}/{y}.png' in url for url in tile_requests), tile_requests[-12:]
        await page.locator('#locationMap .map-pin.environment').click()
        assert 'Thành phố Hồ Chí Minh' in await page.locator('.leaflet-popup-content').inner_text()
        await page.locator('.leaflet-popup-close-button').click()
        await page.locator('.leaflet-popup-content').wait_for(state='detached')
        await page.locator('.leaflet-control-zoom-in').click()
        await page.locator('#mapRecenter').click()
        await page.locator('.location-map-card').scroll_into_view_if_needed()
        await page.wait_for_timeout(700)
        await page.screenshot(path=str(OUTPUT / 'map-desktop.png'))
        await page.set_viewport_size({'width': 390, 'height': 844})
        await page.locator('.location-map-card').scroll_into_view_if_needed()
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await page.locator('#mapRecenter').click()
        await page.wait_for_timeout(700)
        await page.screenshot(path=str(OUTPUT / 'map-mobile.png'))
        await page.reload(wait_until='domcontentloaded')
        await ready(page)
        assert 'Hồ Chí Minh' in await page.locator('#mapLocationLabel').inner_text()
        print('Live map: Hanoi has two reference markers; TP.HCM removes old markers, correct tiles/coordinates/popup/link, zoom/recenter, remembered selection and mobile layout OK.', flush=True)

        # Simulate an unavailable tile provider, then recover without reloading the page.
        await page.route('https://tile.openstreetmap.org/**', lambda route: route.abort())
        await page.locator('#locationSelect').select_option('hue')
        await ready(page)
        await page.locator('#mapRetry').wait_for(state='visible')
        assert await page.locator('#locationMap .map-pin.environment').count() == 1
        assert 'Huế' in await page.locator('#mapLocationLabel').inner_text()
        await page.unroute('https://tile.openstreetmap.org/**')
        await page.locator('#mapRetry').click()
        await page.wait_for_function("document.querySelector('#mapRetry').hidden && document.querySelectorAll('#locationMap img.leaflet-tile-loaded').length > 0", timeout=30000)
        assert not errors, errors
        print('Tile outage: selected point remains visible, retry restores the background; no JavaScript errors.', flush=True)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
