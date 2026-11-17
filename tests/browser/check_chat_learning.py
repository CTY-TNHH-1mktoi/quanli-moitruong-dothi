"""Verify automatic chat learning through the real UI/API with isolated storage."""
import asyncio
import json
import logging
from pathlib import Path
import sys
import tempfile
from threading import Thread
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import app as backend
import chat_knowledge as knowledge
from chat_feedback import FeedbackStore, feedback_events
from chat_learning import ConversationLearner


async def main():
    output = ROOT / '.runtime/test-results/chat-learning'
    output.mkdir(parents=True, exist_ok=True)
    snapshots = {row['DiaDiem']['MaDiaDiem']: row for row in json.loads(
        (ROOT / 'tests/fixtures/locations.json').read_text(encoding='utf-8'))}
    catalogue = json.loads((ROOT / 'locations.json').read_text(encoding='utf-8'))
    logging.getLogger('werkzeug').disabled = True
    with tempfile.TemporaryDirectory(prefix='chat-learning-browser-') as temporary:
        learner = ConversationLearner(Path(temporary) / 'questions.sqlite3', base_dir=Path(temporary) / 'base')
        backend.conversation_learner = learner
        backend.feedback_store = FeedbackStore(Path(temporary) / 'feedback.sqlite3')
        backend.chat_snapshot = lambda location, message, history: {'DiaDiem': location, 'DuLieu': {}}
        fallback = 'Một câu trả lời giả lập chưa xác minh.'
        backend.stream_reply = lambda *args: feedback_events({'reply': fallback, 'truncated': False})
        server = make_server('127.0.0.1', 0, backend.app, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(channel='msedge', headless=True)
                page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors, posts = [], []
                page.on('pageerror', lambda error: errors.append(str(error)))
                async def api(route):
                    parsed = urlparse(route.request.url)
                    if parsed.path == '/api/chat':
                        posts.append(route.request.post_data_json)
                        return await route.continue_()
                    if parsed.path == '/api/diadiem':
                        return await route.fulfill(json={'MacDinh': 'hanoi', 'DiaDiem': catalogue})
                    if parsed.path == '/api/chat/status':
                        return await route.fulfill(json={'state': 'ready'})
                    if parsed.path == '/api/capnhat':
                        identifier = parse_qs(parsed.query).get('location', ['hanoi'])[0]
                        return await route.fulfill(json=snapshots.get(identifier, snapshots['hanoi']))
                    if parsed.path.startswith('/api/bando'):
                        return await route.fulfill(json={'samples': [], 'points': [], 'features': []})
                    return await route.fulfill(json=[])
                await page.route('**/api/**', api)
                base = f'http://127.0.0.1:{server.server_port}'
                await page.goto(base, wait_until='domcontentloaded')
                await page.wait_for_function("!document.querySelector('#locationSelect').disabled")
                await page.locator('#chatLauncher').click()
                assert not learner.path.exists()

                async def ask(message):
                    await page.locator('#chatInput').fill(message)
                    await page.locator('#chatSend').click()
                    await page.wait_for_function("!document.querySelector('#chatSend').disabled")
                    return await page.locator('.chat-message.assistant').last.locator('p').inner_text()

                question = 'Bạn diễn giải PM2.5 là gì cho người mới tìm hiểu giúp mình nhé?'
                first = await ask(question)
                assert 'micromet' in first and 'phổi' in first
                assert learner.stats() == {'learned': 1}
                assert all(post.get('learn_from_chat') is True for post in posts)
                assert await ask(question) == first
                assert learner.questions()[0]['seen_count'] == 2
                await ask('hữu ích')
                assert len(backend.feedback_store.list()) == 1
                followup = await ask('Nó có thể đi sâu vào phổi không?')
                assert 'phổi' in followup and followup != fallback
                assert learner.stats() == {'learned': 2}
                await ask('Ngày mai Hà Nội AQI bao nhiêu?')
                await ask('Môi trường đô thị có xử lý PFAS bằng plasma lạnh được không?')
                counts = learner.stats()
                assert counts == {'learned': 2, 'needs_data': 1, 'needs_source': 1}, counts
                assert len(learner.training_records()) == 2
                assert fallback not in json.dumps(learner.questions(), ensure_ascii=False)

                # A new page and learner instance still reuse the checked lesson.
                backend.conversation_learner = ConversationLearner(learner.path, base_dir=Path(temporary) / 'base')
                await page.reload(wait_until='domcontentloaded')
                await page.wait_for_function("!document.querySelector('#locationSelect').disabled")
                await page.locator('#chatLauncher').click()
                with patch.object(knowledge, 'concept_answer', side_effect=AssertionError('Use saved checked lesson')), \
                     patch.object(knowledge, 'practical_answer', side_effect=AssertionError('Use saved checked lesson')):
                    assert await ask(question) == first
                assert await page.locator('.chat-feedback').count() == 0
                await page.screenshot(path=str(output / 'desktop.png'))
                await page.set_viewport_size({'width': 390, 'height': 844})
                assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                await page.screenshot(path=str(output / 'mobile.png'))
                assert not errors, errors
                result = {'successful': True, 'synthetic_test_data_only': True, 'production_stores_untouched': True,
                          'counts': counts, 'checks': ['automatic_capture_without_vote', 'checked_answer', 'deduplication',
                          'followup_context_after_feedback', 'runtime_data_excluded', 'unknown_answer_not_self_trained',
                          'persistent_alias_reuse', 'frontend_learning_flag', 'no_feedback_buttons', 'desktop_mobile'],
                          'javascript_errors': errors}
                (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                print(json.dumps(result, ensure_ascii=False), flush=True)
                await browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    asyncio.run(main())
