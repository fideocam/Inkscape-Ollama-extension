#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""InkscapeGPT — chat with local Ollama to create, change, and review SVG documents."""

from __future__ import annotations

import queue
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Optional

import inkex

# Ensure sibling modules resolve when Inkscape runs this script directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from apply_actions import apply_actions, extract_actions_json  # noqa: E402
from config import load_config, save_config  # noqa: E402
from context_builder import build_document_digest  # noqa: E402
from ollama_client import (  # noqa: E402
    chat_completion,
    check_connection,
    ensure_ollama_ready,
    get_model_context_settings,
    list_model_names,
    resolve_model_name,
)
from system_prompt import (  # noqa: E402
    SYSTEM_PROMPT,
    build_review_mode_user_message,
    build_user_message,
)

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk
except ImportError:  # pragma: no cover
    Gtk = None  # type: ignore
    GLib = None  # type: ignore


_result_queue: queue.Queue = queue.Queue(maxsize=256)
_cancel_event = threading.Event()
_worker_thread: Optional[threading.Thread] = None
_active_request_id = 0


def _log(message: str) -> None:
    print(f"InkscapeGPT: {message}", file=sys.stderr)


class InkscapeGPTDialog:
    """GTK chat dialog; runs Ollama in a worker thread and applies SVG actions on the main loop."""

    def __init__(
        self,
        svg: inkex.SvgDocumentElement,
        selection: list[Any],
        *,
        review_mode: bool = False,
    ) -> None:
        if Gtk is None:
            raise RuntimeError("GTK 3 is required for InkscapeGPT dialog.")
        self.svg = svg
        self.selection = selection
        self.review_mode = review_mode
        self.config = load_config()
        self.busy = False
        self._poll_id: Optional[int] = None
        self._request_id = 0

        self.window = Gtk.Window(title="InkscapeGPT")
        self.window.set_default_size(720, 640)
        self.window.set_border_width(10)
        self.window.connect("delete-event", self._on_close)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.window.add(outer)

        # Model row
        model_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        model_row.pack_start(Gtk.Label(label="Ollama model:", xalign=0), False, False, 0)
        self.model_combo = Gtk.ComboBoxText.new_with_entry()
        self.model_combo.set_entry_text_column(0)
        self.model_combo.set_hexpand(True)
        model_row.pack_start(self.model_combo, True, True, 0)
        refresh_btn = Gtk.Button(label="Refresh models")
        refresh_btn.connect("clicked", self._on_refresh_models)
        model_row.pack_start(refresh_btn, False, False, 0)
        outer.pack_start(model_row, False, False, 0)

        # Settings row
        settings = Gtk.Expander(label="Settings")
        settings_box = Gtk.Grid(column_spacing=6, row_spacing=4, margin=6)
        settings.add(settings_box)

        settings_box.attach(Gtk.Label(label="Ollama URL:", xalign=0), 0, 0, 1, 1)
        self.base_url_entry = Gtk.Entry()
        self.base_url_entry.set_text(str(self.config.get("base_url", "")))
        settings_box.attach(self.base_url_entry, 1, 0, 2, 1)

        settings_box.attach(Gtk.Label(label="num_ctx (0=auto):", xalign=0), 0, 1, 1, 1)
        self.num_ctx_spin = Gtk.SpinButton.new_with_range(0, 262144, 512)
        self.num_ctx_spin.set_value(float(self.config.get("num_ctx", 0)))
        settings_box.attach(self.num_ctx_spin, 1, 1, 1, 1)

        settings_box.attach(Gtk.Label(label="Max document chars:", xalign=0), 0, 2, 1, 1)
        self.max_chars_spin = Gtk.SpinButton.new_with_range(2000, 500000, 1000)
        self.max_chars_spin.set_value(float(self.config.get("max_context_chars", 48000)))
        settings_box.attach(self.max_chars_spin, 1, 2, 1, 1)

        self.auto_wake_check = Gtk.CheckButton(label="Auto-start Ollama")
        self.auto_wake_check.set_active(bool(self.config.get("auto_wake_ollama", True)))
        settings_box.attach(self.auto_wake_check, 0, 3, 2, 1)

        self.preload_check = Gtk.CheckButton(label="Preload model on ask")
        self.preload_check.set_active(bool(self.config.get("preload_model", True)))
        settings_box.attach(self.preload_check, 0, 4, 2, 1)

        sync_btn = Gtk.Button(label="Sync context from model")
        sync_btn.connect("clicked", self._on_sync_context)
        settings_box.attach(sync_btn, 0, 5, 1, 1)
        ping_btn = Gtk.Button(label="Test connection")
        ping_btn.connect("clicked", self._on_ping)
        settings_box.attach(ping_btn, 1, 5, 1, 1)

        outer.pack_start(settings, False, False, 0)

        # Prompt
        outer.pack_start(Gtk.Label(label="Prompt:", xalign=0), False, False, 0)
        prompt_scroll = Gtk.ScrolledWindow()
        prompt_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        prompt_scroll.set_min_content_height(120)
        self.prompt_view = Gtk.TextView()
        self.prompt_view.set_wrap_mode(Gtk.WrapMode.WORD)
        prompt_scroll.add(self.prompt_view)
        outer.pack_start(prompt_scroll, True, True, 0)

        # Buttons
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.send_btn = Gtk.Button(label="Ask InkscapeGPT")
        self.send_btn.connect("clicked", self._on_send)
        btn_row.pack_start(self.send_btn, False, False, 0)
        self.review_btn = Gtk.Button(label="Review design")
        self.review_btn.connect("clicked", self._on_review)
        btn_row.pack_start(self.review_btn, False, False, 0)
        self.stop_btn = Gtk.Button(label="Stop")
        self.stop_btn.set_sensitive(False)
        self.stop_btn.connect("clicked", self._on_stop)
        btn_row.pack_start(self.stop_btn, False, False, 0)
        outer.pack_start(btn_row, False, False, 0)

        self.status_label = Gtk.Label(label="Ready.", xalign=0)
        self.status_label.set_line_wrap(True)
        outer.pack_start(self.status_label, False, False, 0)

        # Response
        outer.pack_start(Gtk.Label(label="Response:", xalign=0), False, False, 0)
        resp_scroll = Gtk.ScrolledWindow()
        resp_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        resp_scroll.set_min_content_height(180)
        self.response_view = Gtk.TextView()
        self.response_view.set_editable(True)
        self.response_view.set_wrap_mode(Gtk.WrapMode.WORD)
        resp_scroll.add(self.response_view)
        outer.pack_start(resp_scroll, True, True, 0)

        self._populate_models()
        if review_mode:
            self._set_prompt_text("Review this document for layout, SVG hygiene, and export readiness.")

    def run(self) -> None:
        self.window.show_all()
        Gtk.main()

    def _set_prompt_text(self, text: str) -> None:
        buf = self.prompt_view.get_buffer()
        buf.set_text(text)

    def _get_prompt_text(self) -> str:
        buf = self.prompt_view.get_buffer()
        start, end = buf.get_bounds()
        return buf.get_text(start, end, False).strip()

    def _set_response_text(self, text: str) -> None:
        buf = self.response_view.get_buffer()
        buf.set_text(text)

    def _set_status(self, text: str) -> None:
        self.status_label.set_text(text[:500])

    def _save_settings(self) -> None:
        self.config["base_url"] = self.base_url_entry.get_text().strip()
        self.config["model"] = self._get_model_text()
        self.config["num_ctx"] = int(self.num_ctx_spin.get_value())
        self.config["max_context_chars"] = int(self.max_chars_spin.get_value())
        self.config["auto_wake_ollama"] = self.auto_wake_check.get_active()
        self.config["preload_model"] = self.preload_check.get_active()
        save_config(self.config)

    def _get_model_text(self) -> str:
        entry = self.model_combo.get_child()
        if entry is not None:
            return entry.get_text().strip()
        return str(self.config.get("model", "llama3.2:latest"))

    def _populate_models(self) -> None:
        self.model_combo.remove_all()
        model = str(self.config.get("model", "llama3.2:latest"))
        names: list[str] = []
        try:
            names = list_model_names(self.base_url_entry.get_text().strip())
        except Exception as exc:
            self._set_status(f"Could not list models: {exc}")
        if model and model not in names:
            names.insert(0, model)
        for name in names:
            self.model_combo.append_text(name)
        if names:
            self.model_combo.set_active(0)
        entry = self.model_combo.get_child()
        if entry is not None:
            entry.set_text(model)

    def _on_refresh_models(self, *_args: Any) -> None:
        self._save_settings()
        self._populate_models()
        self._set_status("Model list refreshed.")

    def _on_sync_context(self, *_args: Any) -> None:
        self._save_settings()
        base_url = self.config["base_url"]
        model = self._get_model_text()
        try:
            model = resolve_model_name(base_url, model)
            info = get_model_context_settings(base_url, model)
            if info.get("num_ctx"):
                self.num_ctx_spin.set_value(float(info["num_ctx"]))
            if info.get("max_document_chars"):
                self.max_chars_spin.set_value(float(info["max_document_chars"]))
            self._save_settings()
            self._set_status(info.get("summary", "Context synced."))
        except Exception as exc:
            self._set_status(f"Sync failed: {exc}")

    def _on_ping(self, *_args: Any) -> None:
        self._save_settings()
        base_url = self.config["base_url"]
        try:
            if self.auto_wake_check.get_active():
                ensure_ollama_ready(
                    base_url,
                    self._get_model_text(),
                    preload_model=self.preload_check.get_active(),
                    num_ctx=int(self.num_ctx_spin.get_value()),
                    try_launch=True,
                )
            elif not check_connection(base_url):
                raise RuntimeError("Ollama is not reachable.")
            self._set_status("Ollama connection OK.")
        except Exception as exc:
            self._set_status(f"Connection failed: {exc}")

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.send_btn.set_sensitive(not busy)
        self.review_btn.set_sensitive(not busy)
        self.stop_btn.set_sensitive(busy)
        self.prompt_view.set_sensitive(not busy)

    def _on_send(self, *_args: Any) -> None:
        self.review_mode = False
        self._start_request()

    def _on_review(self, *_args: Any) -> None:
        self.review_mode = True
        self._start_request()

    def _on_stop(self, *_args: Any) -> None:
        global _active_request_id
        _cancel_event.set()
        _active_request_id += 1
        self._set_busy(False)
        self._set_status("Stopping…")

    def _start_request(self) -> None:
        global _active_request_id, _worker_thread

        prompt = self._get_prompt_text()
        if not prompt:
            self._set_status("Enter a prompt first.")
            return

        self._save_settings()
        _cancel_event.clear()

        max_chars = int(self.max_chars_spin.get_value())
        digest = build_document_digest(self.svg, self.selection, max_chars)
        if self.review_mode:
            user_msg = build_review_mode_user_message(digest, prompt)
        else:
            user_msg = build_user_message(digest, prompt)

        base_url = self.config["base_url"]
        model = self._get_model_text()
        num_ctx = int(self.num_ctx_spin.get_value())
        timeout = float(self.config.get("request_timeout", 600))

        try:
            model = resolve_model_name(base_url, model)
        except Exception as exc:
            self._set_status(str(exc))
            return

        _active_request_id += 1
        self._request_id = _active_request_id
        self._set_busy(True)
        self._set_status("Starting request…")
        self._set_response_text("")

        while True:
            try:
                _result_queue.get_nowait()
            except queue.Empty:
                break

        def worker() -> None:
            try:
                if self.config.get("auto_wake_ollama") or self.config.get("preload_model"):
                    ensure_ollama_ready(
                        base_url,
                        model,
                        preload_model=bool(self.config.get("preload_model")),
                        num_ctx=num_ctx,
                        try_launch=bool(self.config.get("auto_wake_ollama")),
                        cancel_event=_cancel_event,
                    )

                def on_token(partial: str) -> None:
                    try:
                        _result_queue.put_nowait((self._request_id, "stream", partial))
                    except queue.Full:
                        pass

                text = chat_completion(
                    base_url,
                    model,
                    SYSTEM_PROMPT,
                    user_msg,
                    num_ctx=num_ctx,
                    cancel_event=_cancel_event,
                    timeout=timeout,
                    progress_cb=on_token,
                )
                _result_queue.put((self._request_id, "ok", text))
            except InterruptedError:
                _result_queue.put((self._request_id, "cancel", ""))
            except Exception as exc:
                traceback.print_exc()
                _result_queue.put((self._request_id, "err", str(exc)))

        _worker_thread = threading.Thread(target=worker, daemon=True)
        _worker_thread.start()

        if self._poll_id is None:
            self._poll_id = GLib.timeout_add(120, self._poll_results)

    def _poll_results(self) -> bool:
        global _active_request_id
        try:
            while True:
                item = _result_queue.get_nowait()
                req_id, kind, payload = item
                if req_id != self._request_id or req_id != _active_request_id:
                    continue
                if kind == "stream":
                    self._set_response_text(str(payload))
                    self._set_status(f"Receiving… ({len(str(payload))} chars)")
                elif kind == "ok":
                    text = str(payload)
                    self._set_response_text(text)
                    actions = extract_actions_json(text)
                    if actions:
                        logs = apply_actions(self.svg, actions)
                        status = f"Applied {len(actions)} action(s)."
                        if logs:
                            status += " " + "; ".join(logs[:8])
                            if len(logs) > 8:
                                status += f" (+{len(logs) - 8} more)"
                    else:
                        status = "Reply received (no actions to apply)."
                    self._set_status(status)
                    self._set_busy(False)
                elif kind == "cancel":
                    self._set_status("Cancelled.")
                    self._set_busy(False)
                elif kind == "err":
                    self._set_status(f"Error: {payload}")
                    self._set_busy(False)
        except queue.Empty:
            pass
        return True

    def _on_close(self, *_args: Any) -> bool:
        if self.busy:
            self._on_stop()
        self._save_settings()
        Gtk.main_quit()
        return False


class InkscapeGPTExtension(inkex.EffectExtension):
    """Open InkscapeGPT chat dialog for the current document."""

    def effect(self) -> None:
        selection = list(self.svg.selection)
        dialog = InkscapeGPTDialog(self.svg, selection)
        dialog.run()


class InkscapeGPTReviewExtension(inkex.EffectExtension):
    """Open InkscapeGPT in review mode."""

    def effect(self) -> None:
        selection = list(self.svg.selection)
        dialog = InkscapeGPTDialog(self.svg, selection, review_mode=True)
        dialog.run()


if __name__ == "__main__":
    InkscapeGPTExtension().run()
