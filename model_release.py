"""Resolve an explicitly activated local Xanh Non release."""

import json
import hashlib
import logging
from pathlib import Path


def read_release(root):
    root = Path(root).resolve()
    manifest = root / "models" / "xanhnon-active.json"
    if not manifest.is_file():
        return {}
    try:
        release = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(release, dict) or release.get("version") != 1:
            raise ValueError("Unsupported release version")
        result = {"name": release["name"]}
        for key in ("gguf", "adapter", "base_model"):
            path = (root / release[key]).resolve()
            if not path.is_relative_to(root / "models"):
                raise ValueError("Release files must remain inside models")
            result[key] = path
        if not result["gguf"].is_file():
            raise FileNotFoundError("Activated GGUF is missing")
        if not (result["base_model"] / "model.safetensors").is_file():
            raise FileNotFoundError("Base weights are missing")
        if (not (result["adapter"] / "adapter_config.json").is_file()
                or not (result["adapter"] / "adapter_model.safetensors").is_file()):
            # The recovered GGUF already contains the Style-v2 adaptation.
            # Only allow native-only recovery after matching its recorded hash.
            expected = release.get('gguf_sha256')
            digest = hashlib.sha256()
            if not isinstance(expected, str) or len(expected) != 64:
                raise FileNotFoundError('Standalone adapter missing; no verified GGUF hash')
            with result['gguf'].open('rb') as handle:
                for block in iter(lambda: handle.read(4*1024*1024), b''):
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise ValueError('Recovered GGUF checksum mismatch')
            result['adapter'] = None
        return result
    except (OSError, ValueError, KeyError, TypeError):
        logging.getLogger(__name__).warning("Không nạp được bản Xanh Non đã kích hoạt; dùng mô hình gốc", exc_info=True)
        return {}
