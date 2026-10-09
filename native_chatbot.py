"""Manage an owned llama.cpp CPU process and stream its local chat responses."""

import atexit
import json
import os
from pathlib import Path
import socket
import subprocess
import time

import requests


class NativeChatbot:
    def __init__(self, binary, model_path, threads, max_input_tokens, max_output_tokens):
        self.max_input_tokens = max_input_tokens
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        log_path = Path(binary).parent.parent / "xanhnon-server.log"
        arguments = [
            str(binary), "-m", str(model_path), "-t", str(threads), "-tb", str(threads),
            "-c", str(max_input_tokens + max(max_output_tokens, 2048)),
            "-b", "256", "-ub", "128", "-np", "1",
            "-n", str(max_output_tokens), "--context-shift", "--keep", "-1",
            "--host", "127.0.0.1", "--port", str(port), "-ngl", "0",
        ]
        with log_path.open("ab") as log:
            self.process = subprocess.Popen(
                arguments, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        atexit.register(self.close)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(f"llama.cpp exited; see {log_path}")
                try:
                    if requests.get(self.base_url + "/health", timeout=1).status_code == 200:
                        return
                except requests.RequestException:
                    pass
                time.sleep(0.25)
            raise TimeoutError("llama.cpp did not become ready")
        except Exception:
            self.close()
            raise

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def _prepare_messages(self, messages):
        messages = list(messages)
        while True:
            response = requests.post(
                self.base_url + "/apply-template", json={"messages": messages}, timeout=(3, 15),
            )
            response.raise_for_status()
            prompt = response.json()["prompt"]
            response = requests.post(
                self.base_url + "/tokenize", json={"content": prompt}, timeout=(3, 15),
            )
            response.raise_for_status()
            if len(response.json()["tokens"]) <= self.max_input_tokens:
                return messages
            if len(messages) <= 2:
                raise ValueError("Câu hỏi quá dài với ngữ cảnh hiện tại. Hãy rút ngắn câu hỏi.")
            del messages[1:3]

    def generate(self, messages, max_tokens, on_text=None, cancelled=None):
        messages = self._prepare_messages(messages)
        parts = []
        finish_reason = None
        payload = {
            "messages": messages, "max_tokens": max_tokens, "stream": True,
            "temperature": 0, "top_k": 1, "top_p": 1, "repeat_penalty": 1.1,
            "cache_prompt": True,
        }
        with requests.post(
            self.base_url + "/v1/chat/completions", json=payload,
            stream=True, timeout=(3, None),
        ) as response:
            response.raise_for_status()
            response.encoding = "utf-8"
            for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                if cancelled is not None and cancelled.is_set():
                    break
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                event = json.loads(data)
                if "error" in event:
                    raise RuntimeError("llama.cpp generation failed")
                choices = event.get("choices", [])
                if not choices:
                    continue
                choice = choices[0]
                text = choice.get("delta", {}).get("content", "")
                if text:
                    parts.append(text)
                    if on_text is not None:
                        on_text(text)
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]
        reply = "".join(parts).strip()
        if not reply:
            raise RuntimeError("The model returned an empty reply")
        return {"reply": reply, "truncated": finish_reason != "stop"}
