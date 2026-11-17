"""Check nearest-place selection without recording data or sending device coordinates."""
import json
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright, expect

from common import BASE, OUTPUT, ROOT

PLACES = json.loads((ROOT / 'locations.json').read_text(encoding='utf-8'))
BY_ID = {place['MaDiaDiem']: place for place in PLACES}


def open_page(browser, width=1600, geolocation=None, init_script=None):
    context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce',
                                  permissions=['geolocation'], geolocation=geolocation or {'latitude': 21.23, 'longitude': 105.72})
    calls, errors = [], []

    def mock(route):
        parsed = urlparse(route.request.url)
        calls.append({'path': parsed.path, 'query': parse_qs(parsed.query), 'body': route.request.post_data})
        place = BY_ID[parse_qs(parsed.query).get('location', ['hanoi'])[0]]
        if parsed.path == '/api/diadiem': data = {'DiaDiem': PLACES, 'MacDinh': 'hanoi'}
        elif parsed.path == '/api/capnhat':
            data = {'DiaDiem': place, 'ThoiGian': '2026-10-19T09:30:00',
                    'DuLieu': {'US_AQI': 95, 'PM25': 36.4, 'PM10': 40, 'NhietDo': 27, 'DoAm': 72, 'TiengOn': 65}}
        elif parsed.path == '/api/bando/khongkhi':
            data = {'DiaDiem': place, 'SoDiem': 0, 'ViDo': [], 'KinhDo': [], 'AQI': []}
        elif parsed.path == '/api/chat/status': data = {'state': 'training'}
        else: data = []
        route.fulfill(json=data)

    context.route('**/api/**', mock)
    context.route('https://**/*', lambda route: route.abort())
    context.add_init_script("""window.positionRequests = 0;
      const locate = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation);
      navigator.geolocation.getCurrentPosition = (...args) => { window.positionRequests++; return locate(...args); };
    """ + (init_script or ''))
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE, wait_until='domcontentloaded')
    expect(page.locator('#locateMe')).to_be_enabled()
    expect(page.locator('#mainContent')).to_have_attribute('aria-busy', 'false')
    return context, page, calls, errors


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        try:
            for width in (1600, 390):
                context, page, calls, errors = open_page(browser, width)
                assert page.evaluate('window.positionRequests') == 0, 'Position must be requested only on click'
                expect(page.locator('#geolocationStatus')).to_be_hidden()
                for identifier, latitude, longitude in [
                    ('noise-ba2df08c3226', 21.23, 105.72),
                    ('tphcm', 10.825, 106.63),
                    ('noise-7ec288de7004', 21.019, 105.802),
                ]:
                    context.set_geolocation({'latitude': latitude, 'longitude': longitude, 'accuracy': 20})
                    page.locator('#locateMe').click()
                    expect(page.locator('#locationSelect')).to_have_value(identifier)
                    expect(page.locator('#geolocationStatus')).to_have_attribute('data-state', 'success')
                    expect(page.locator('#geolocationStatus')).to_contain_text(BY_ID[identifier]['Ten'])
                    expect(page.locator('#locationTitle')).to_have_text(BY_ID[identifier]['Ten'])
                    expect(page.locator('#mainContent')).to_have_attribute('aria-busy', 'false')
                    expect(page.locator('#locateMe')).to_be_enabled()
                    assert any(call['path'] == '/api/capnhat' and call['query'].get('location') == [identifier] for call in calls)
                    assert page.evaluate("localStorage.getItem('environment.location.v1')") == identifier
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                # The select retains its short width, with the button beside it on desktop.
                select_box = page.locator('#locationSelect').bounding_box()
                button_box = page.locator('#locateMe').bounding_box()
                assert select_box['width'] <= 351
                if width > 991: assert abs(select_box['y'] - button_box['y']) < 2
                page.screenshot(path=str(OUTPUT / f'geolocation-{width}.png'))
                page.reload(wait_until='domcontentloaded')
                expect(page.locator('#locationSelect')).to_have_value('noise-7ec288de7004')
                expect(page.locator('#locateMe')).to_be_enabled()
                assert page.evaluate('window.positionRequests') == 0
                # Raw device coordinates are never part of API query parameters or bodies.
                assert all(not ({'latitude', 'longitude', 'lat', 'lon'} & call['query'].keys()) and call['body'] is None for call in calls)
                assert not errors, errors
                results.append({'width': width, 'nearest_selection_refresh_and_persistence': 'passed', 'javascript_errors': errors})
                context.close()

            script = """Object.defineProperty(navigator, 'geolocation', {value: {
              getCurrentPosition(success, failure) { window.positionRequests++; window.positionSuccess = success; window.positionFailure = failure; }
            }});"""
            context, page, _, errors = open_page(browser, init_script=script)
            for code, text in [(1, 'quyền vị trí'), (2, 'dịch vụ vị trí'), (3, 'quá lâu')]:
                page.locator('#locateMe').click()
                expect(page.locator('#locateMe')).to_be_disabled()
                expect(page.locator('#locationSelect')).to_be_enabled()
                page.evaluate('(code) => window.positionFailure({code})', code)
                expect(page.locator('#geolocationStatus')).to_have_attribute('data-state', 'error')
                expect(page.locator('#geolocationStatus')).to_contain_text(text)
                expect(page.locator('#locationSelect')).to_have_value('hanoi')
                expect(page.locator('#locateMe')).to_be_enabled()
            page.locator('#locateMe').click()
            page.locator('#locationSelect').select_option('danang')
            page.evaluate('window.positionSuccess({coords: {latitude: 10.825, longitude: 106.63}})')
            expect(page.locator('#locationSelect')).to_have_value('danang')
            expect(page.locator('#geolocationStatus')).to_be_hidden()
            expect(page.locator('#locateMe')).to_be_enabled()
            page.evaluate("window.EnvironmentLocation.setBusy('chat', true)")
            expect(page.locator('#locateMe')).to_be_disabled()
            page.evaluate("window.EnvironmentLocation.setBusy('chat', false)")
            expect(page.locator('#locateMe')).to_be_enabled()
            page.locator('#locateMe').click()
            page.evaluate('window.positionSuccess({coords: {latitude: 999, longitude: 0}})')
            expect(page.locator('#geolocationStatus')).to_have_attribute('data-state', 'error')
            expect(page.locator('#locationSelect')).to_have_value('danang')
            assert not errors, errors
            context.close()

            context, page, _, errors = open_page(browser, init_script="Object.defineProperty(navigator, 'geolocation', {value: undefined});")
            page.locator('#locateMe').click()
            expect(page.locator('#geolocationStatus')).to_contain_text('chưa hỗ trợ')
            expect(page.locator('#locationSelect')).to_be_enabled()
            assert not errors, errors
            context.close()
            results.append({'permission_unavailable_timeout_invalid_position_manual_override_busy_and_unsupported': 'passed'})
        finally:
            browser.close()
    (OUTPUT / 'geolocation-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False))


if __name__ == '__main__':
    main()
