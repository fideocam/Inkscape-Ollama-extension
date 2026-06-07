"""HTTP client for Ollama /api/chat (streaming) and /api/show (model metadata)."""

from __future__ import annotations

import json
import platform
import re
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Optional

_DEFAULT_RESERVE_TOKENS = 12_000
_CHARS_PER_TOKEN = 3.5


def _normalize_base(url: str) -> str:
    return (url or "").strip().rstrip("/")


def chat_completion(
    base_url: str,
    model: str,
    system: str,
    user: str,
    num_ctx: int = 0,
    cancel_event: Optional[threading.Event] = None,
    timeout: float = 600.0,
    progress_cb: Optional[Any] = None,
) -> str:
    """
    POST /api/chat with stream:true, reassembling tokens.
    progress_cb(partial_text) is called after each token chunk if provided.
    """
    base = _normalize_base(base_url)
    payload: dict[str, Any] = {
        "model": model,
        "stream": True,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if num_ctx and num_ctx > 0:
        payload["options"] = {"num_ctx": int(num_ctx)}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    ctx = ssl.create_default_context()
    chunks: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            for raw_line in resp:
                if cancel_event is not None and cancel_event.is_set():
                    raise InterruptedError("Cancelled")
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = (obj.get("message") or {}).get("content", "")
                if token:
                    chunks.append(token)
                    if progress_cb is not None:
                        try:
                            progress_cb("".join(chunks))
                        except Exception:
                            pass
                if obj.get("done"):
                    break
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(f"Ollama HTTP {e.code}: {err_body or e.reason}") from e
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        raise RuntimeError(
            f"Cannot reach Ollama at {base}. Is it running? ({reason})"
        ) from e
    except TimeoutError as e:
        raise RuntimeError(
            f"Ollama request timed out after {int(timeout)}s. "
            "Try a smaller model, lower document context, or Stop and retry."
        ) from e

    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("Cancelled")

    return "".join(chunks)


def _post_json(base_url: str, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    base = _normalize_base(base_url)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(f"Ollama HTTP {e.code}: {err_body or e.reason}") from e
    try:
        obj = json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from Ollama: {body[:500]}") from e
    if not isinstance(obj, dict):
        raise RuntimeError(f"Unexpected Ollama response shape: {str(obj)[:500]}")
    return obj


def show_model(base_url: str, model: str, timeout: float = 10.0) -> dict[str, Any]:
    return _post_json(base_url, "/api/show", {"model": model}, timeout)


def parse_parameters_num_ctx(parameters: Any) -> Optional[int]:
    if isinstance(parameters, dict):
        raw = parameters.get("num_ctx")
        if isinstance(raw, (int, float)):
            return max(512, int(raw))
        if isinstance(raw, str) and raw.strip().isdigit():
            return max(512, int(raw.strip()))
    if not isinstance(parameters, str):
        return None
    for line in parameters.splitlines():
        stripped = line.strip()
        if not stripped.lower().startswith("num_ctx"):
            continue
        parts = stripped.split()
        if len(parts) >= 2 and parts[-1].isdigit():
            return max(512, int(parts[-1]))
        m = re.search(r"num_ctx\s+(\d+)", stripped, re.IGNORECASE)
        if m:
            return max(512, int(m.group(1)))
    return None


def parse_model_info_context_length(model_info: Any) -> Optional[int]:
    if not isinstance(model_info, dict):
        return None
    best: Optional[int] = None
    for key, val in model_info.items():
        if "context_length" not in str(key).lower():
            continue
        if isinstance(val, (int, float)) and val > 0:
            n = int(val)
            best = n if best is None else max(best, n)
    return best


def suggest_max_document_chars(
    num_ctx: int,
    *,
    reserve_tokens: int = _DEFAULT_RESERVE_TOKENS,
    chars_per_token: float = _CHARS_PER_TOKEN,
    max_chars: int = 500_000,
) -> int:
    usable_tokens = max(512, num_ctx - reserve_tokens)
    return min(max_chars, max(2000, int(usable_tokens * chars_per_token)))


def resolve_context_settings(show_data: dict[str, Any]) -> dict[str, Any]:
    model_max = parse_model_info_context_length(show_data.get("model_info"))
    configured = parse_parameters_num_ctx(show_data.get("parameters"))

    if model_max and configured:
        num_ctx = min(model_max, configured)
        source = "model_info and parameters"
    elif model_max:
        num_ctx = model_max
        source = "model_info"
    elif configured:
        num_ctx = configured
        source = "parameters"
    else:
        return {
            "num_ctx": 0,
            "max_document_chars": 48_000,
            "model_context_max": None,
            "configured_num_ctx": None,
            "summary": "No context length in /api/show; using Ollama runtime default and 48k document chars.",
        }

    max_document = suggest_max_document_chars(num_ctx)
    return {
        "num_ctx": num_ctx,
        "max_document_chars": max_document,
        "model_context_max": model_max,
        "configured_num_ctx": configured,
        "summary": (
            f"Context {num_ctx:,} tokens ({source}); "
            f"document digest ≤ {max_document:,} chars."
        ),
    }


def get_model_context_settings(base_url: str, model: str, timeout: float = 10.0) -> dict[str, Any]:
    show_data = show_model(base_url, model, timeout=timeout)
    out = resolve_context_settings(show_data)
    out["model"] = show_data.get("model") or model
    return out


def fetch_tags(base_url: str, timeout: float = 5.0) -> dict[str, Any]:
    base = _normalize_base(base_url)
    url = f"{base}/api/tags"
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(f"Ollama HTTP {e.code}: {err_body or e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot reach Ollama at {base}. Is it running? ({getattr(e, 'reason', e)})"
        ) from e
    obj = json.loads(body)
    if not isinstance(obj, dict):
        raise RuntimeError("Invalid /api/tags response from Ollama")
    return obj


def list_model_names(base_url: str, timeout: float = 5.0) -> list[str]:
    data = fetch_tags(base_url, timeout=timeout)
    names: list[str] = []
    for item in data.get("models") or []:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    return names


def resolve_model_name(base_url: str, model: str, timeout: float = 5.0) -> str:
    model = (model or "").strip()
    if not model:
        raise RuntimeError("No model configured.")

    names = list_model_names(base_url, timeout=timeout)
    if not names:
        raise RuntimeError("Ollama returned no models. Run: ollama pull <model>")

    if model in names:
        return model

    if ":" not in model:
        prefixed = [n for n in names if n.split(":")[0] == model or n.startswith(model + ":")]
        if len(prefixed) == 1:
            return prefixed[0]
        if len(prefixed) > 1:
            raise RuntimeError(
                f"Model {model!r} is ambiguous. Use one of: {', '.join(prefixed)}"
            )

    sample = ", ".join(names[:6])
    more = f" (+{len(names) - 6} more)" if len(names) > 6 else ""
    raise RuntimeError(f"Model {model!r} not found in Ollama. Installed: {sample}{more}")


def check_connection(base_url: str, timeout: float = 3.0) -> bool:
    try:
        fetch_tags(base_url, timeout=timeout)
        return True
    except Exception:
        return False


def test_ollama_connection(
    base_url: str,
    model: str,
    *,
    try_launch: bool = True,
    connection_timeout: float = 3.0,
    timeout: float = 10.0,
) -> str:
    """Verify Ollama responds and the configured model is installed."""
    base = _normalize_base(base_url)
    if not wait_for_connection(
        base_url,
        timeout=connection_timeout,
        try_launch=try_launch,
    ):
        raise RuntimeError(
            f"Ollama is not reachable at {base}. "
            "Start the Ollama app or run 'ollama serve', then try again."
        )

    names = list_model_names(base_url, timeout=timeout)
    resolved = resolve_model_name(base_url, model, timeout=timeout)

    lines = [
        f"Connected to Ollama at {base}.",
        f"Model {resolved!r} is available.",
        f"{len(names)} model(s) installed.",
    ]
    try:
        ctx = get_model_context_settings(base_url, resolved, timeout=timeout)
        summary = ctx.get("summary")
        if summary:
            lines.append(str(summary))
    except Exception:
        pass
    return "\n".join(lines)


_warm_cache_lock = threading.Lock()
_warm_cache: dict[tuple[str, str], float] = {}
_WARM_CACHE_TTL = 300.0


def _try_launch_ollama_host() -> bool:
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(
                ["open", "-a", "Ollama"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        if system == "Windows":
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def wait_for_connection(
    base_url: str,
    *,
    attempts: int = 8,
    pause_seconds: float = 1.5,
    timeout: float = 3.0,
    try_launch: bool = True,
) -> bool:
    launched = False
    for attempt in range(attempts):
        if check_connection(base_url, timeout=timeout):
            return True
        if try_launch and not launched and attempt == 0:
            launched = _try_launch_ollama_host()
        if attempt + 1 < attempts:
            time.sleep(pause_seconds)
    return False


def warm_model(
    base_url: str,
    model: str,
    *,
    num_ctx: int = 0,
    timeout: float = 120.0,
    cancel_event: Optional[threading.Event] = None,
) -> None:
    model = (model or "").strip()
    if not model:
        return

    cache_key = (_normalize_base(base_url), model)
    with _warm_cache_lock:
        last = _warm_cache.get(cache_key)
        if last is not None and (time.monotonic() - last) < _WARM_CACHE_TTL:
            return

    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("Cancelled")

    payload: dict[str, Any] = {
        "model": model,
        "prompt": ".",
        "stream": False,
        "options": {"num_predict": 1},
    }
    if num_ctx and num_ctx > 0:
        payload["options"]["num_ctx"] = int(num_ctx)

    _post_json(base_url, "/api/generate", payload, timeout)

    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("Cancelled")

    with _warm_cache_lock:
        _warm_cache[cache_key] = time.monotonic()


def ensure_ollama_ready(
    base_url: str,
    model: str,
    *,
    preload_model: bool = True,
    num_ctx: int = 0,
    connection_timeout: float = 3.0,
    warm_timeout: float = 180.0,
    try_launch: bool = True,
    cancel_event: Optional[threading.Event] = None,
) -> None:
    if not wait_for_connection(
        base_url,
        timeout=connection_timeout,
        try_launch=try_launch,
    ):
        base = _normalize_base(base_url)
        raise RuntimeError(
            f"Ollama is not reachable at {base}. "
            "Start the Ollama app or run 'ollama serve', then try again."
        )

    if preload_model and (model or "").strip():
        warm_model(
            base_url,
            model,
            num_ctx=num_ctx,
            timeout=warm_timeout,
            cancel_event=cancel_event,
        )
