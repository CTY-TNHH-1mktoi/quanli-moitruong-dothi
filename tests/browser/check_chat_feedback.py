"""Exercise opt-in feedback with real SQLite and an isolated local HTTP server."""

import asyncio
import json
import logging
from pathlib import Path
import sys
import tempfile
from threading import Thread
from urllib.parse import parse_qs, urlparse

from flask import Flask
from playwright.async_api import async_playwright
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from chat_feedback import FeedbackStore, create_feedback_blueprint


async def main():
    output = ROOT / ".runtime/test-results/feedback"
    output.mkdir(parents=True, exist_ok=True)
    snapshots = {row["DiaDiem"]["MaDiaDiem"]: row for row in json.loads(
        (ROOT / "tests/fixtures/locations.json").read_text(encoding="utf-8"))}
    catalogue = json.loads((ROOT / "locations.json").read_text(encoding="utf-8"))
    logging.getLogger("werkzeug").disabled = True
    with tempfile.TemporaryDirectory(prefix="feedback-browser-") as temporary:
        store = FeedbackStore(Path(temporary) / "feedback.sqlite3")
        application = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="")
        application.register_blueprint(create_feedback_blueprint(store, lambda: "browser-test"))
        application.add_url_rule("/", view_func=lambda: application.send_static_file("index.html"))
        server = make_server("127.0.0.1", 0, application, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(channel="msedge", headless=True)
                context = await browser.new_context(viewport={"width": 1440, "height": 1000})
                page = await context.new_page()
                errors, requests = [], []
                mode = {"fail_once": True, "delay": False}
                page.on("pageerror", lambda error: errors.append(str(error)))

                async def api(route):
                    parsed = urlparse(route.request.url)
                    path = parsed.path
                    if path == "/api/chat/feedback":
                        requests.append(route.request.post_data_json)
                        if mode["fail_once"]:
                            mode["fail_once"] = False
                            return await route.fulfill(status=503, json={"loi": "Chưa lưu được góp ý. Bạn thử lại nhé."})
                        if mode["delay"]:
                            await asyncio.sleep(.5)
                        return await route.continue_()
                    if path == "/api/diadiem":
                        return await route.fulfill(json={"MacDinh": "hanoi", "DiaDiem": catalogue})
                    if path == "/api/chat/status":
                        return await route.fulfill(json={"state": "ready"})
                    if path == "/api/chat":
                        body = route.request.post_data_json
                        result = {"reply": "Câu trả lời thử nghiệm cho " + body["location"] + ".", "truncated": False}
                        events = [{"type": "delta", "text": result["reply"]}, {"type": "done", **result}]
                        return await route.fulfill(content_type="text/event-stream",
                            body="".join("data: " + json.dumps(event, ensure_ascii=False) + "\n\n" for event in events))
                    if path == "/api/capnhat":
                        location = parse_qs(parsed.query).get("location", ["hanoi"])[0]
                        return await route.fulfill(json=snapshots.get(location, snapshots["hanoi"]))
                    if path.startswith("/api/bando"):
                        return await route.fulfill(json={"samples": [], "points": [], "features": []})
                    return await route.fulfill(json=[])

                await page.route("**/api/**", api)
                await page.goto(base, wait_until="domcontentloaded")
                await page.wait_for_function("!document.querySelector('#locationSelect').disabled")
                assert not store.path.exists(), "Opening the page must not save chat or feedback"
                await page.locator("#chatLauncher").click()
                assert await page.locator(".chat-feedback").count() == 0

                async def ask(message):
                    await page.locator("#chatInput").fill(message)
                    await page.locator("#chatSend").click()
                    await page.wait_for_function("!document.querySelector('#chatSend').disabled")
                    return page.locator(".chat-feedback").last

                feedback = await ask("Thời tiết hôm nay thế nào?")
                assert not store.path.exists(), "Receiving a reply must not save it automatically"
                await feedback.get_by_role("button", name="Góp ý", exact=True).click()
                await feedback.get_by_label("Bạn muốn cải thiện điều gì?").select_option("context")
                await feedback.get_by_label("Góp ý của bạn", exact=True).fill("Cần nhớ chủ đề thời tiết của câu trước.")
                await feedback.get_by_role("button", name="Gửi góp ý", exact=True).click()
                await feedback.locator(".chat-feedback-status").filter(has_text="Chưa lưu").wait_for()
                assert not store.path.exists()
                assert await feedback.get_by_label("Góp ý của bạn", exact=True).input_value()
                await feedback.get_by_role("button", name="Gửi góp ý", exact=True).click()
                await feedback.locator(".chat-feedback-status").filter(has_text="Đã nhận góp ý").wait_for()
                assert await feedback.locator(".chat-feedback-form").is_hidden()
                assert await feedback.locator(".chat-feedback-actions").first.is_hidden()
                assert await feedback.locator(".chat-feedback-note").is_hidden()

                helpful = await ask("Mai thì sao?")
                await helpful.get_by_role("button", name="Hữu ích", exact=True).click()
                await helpful.locator(".chat-feedback-status").filter(has_text="Đã nhận góp ý").wait_for()
                rows = store.list("pending")
                assert len(rows) == 2 and not store.list("approved")
                assert rows[1]["payload"]["history"][0]["content"] == "Thời tiết hôm nay thế nào?"
                assert rows[1]["payload"]["rating"] == "helpful"

                await page.locator("#locationSelect").select_option("tphcm")
                await page.wait_for_function("!document.querySelector('#locationSelect').disabled")
                other = await ask("Thử câu hỏi tại TP.HCM")
                mode["delay"] = True
                async with page.expect_response("**/api/chat/feedback"):
                    await other.get_by_role("button", name="Hữu ích", exact=True).click()
                    await page.locator("#locationSelect").select_option("hanoi")
                await page.wait_for_function("!document.querySelector('#locationSelect').disabled")
                assert await page.locator(".chat-feedback button:visible").count() == 0
                rows = store.list("pending")
                assert rows[-1]["payload"]["location"] == "tphcm"
                assert rows[-1]["payload"]["history"] == []

                await page.screenshot(path=str(output / "desktop.png"))
                await page.set_viewport_size({"width": 390, "height": 844})
                mobile = await ask("Thử góp ý trên màn hình nhỏ")
                await mobile.get_by_role("button", name="Góp ý", exact=True).click()
                await mobile.get_by_label("Góp ý của bạn", exact=True).fill("Muốn câu trả lời tự nhiên và ngắn hơn.")
                assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                box = await mobile.bounding_box()
                assert box and box["x"] >= 0 and box["x"] + box["width"] <= 390
                await page.screenshot(path=str(output / "mobile.png"))
                await page.locator("#chatReset").click()
                assert await page.locator(".chat-feedback").count() == 0
                assert len(store.list("pending")) == 3
                assert not errors, errors
                summary = {"successful": True, "synthetic_test_data_only": True, "production_database_untouched": True,
                           "stored_pending": len(rows), "stored_approved": 0, "feedback_posts": len(requests),
                           "checks": ["opt_in_only", "real_http_sqlite", "failed_save_retry", "sse_reply", "context_capture",
                                      "location_change_while_saving", "sent_state_after_restore", "mobile_layout", "reset"],
                           "javascript_errors": errors}
                (output / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps(summary, ensure_ascii=False), flush=True)
                await browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    asyncio.run(main())
