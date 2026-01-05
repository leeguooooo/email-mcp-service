"""
Telegram interactive helpers for daily digest.
"""
from __future__ import annotations

import html as html_lib
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class TelegramSessionStore:
    def __init__(self, path: str, ttl_hours: int = 48) -> None:
        self.path = Path(path)
        self.ttl = timedelta(hours=ttl_hours)
        self._lock = threading.Lock()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"sessions": {}}
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                return {"sessions": {}}
            if "sessions" not in data or not isinstance(data["sessions"], dict):
                return {"sessions": {}}
            return data
        except Exception:
            return {"sessions": {}}

    def _save(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

    def _is_expired(self, created_at: str) -> bool:
        try:
            created = datetime.fromisoformat(created_at)
        except Exception:
            return True
        return datetime.now() - created > self.ttl

    def cleanup(self) -> None:
        with self._lock:
            data = self._load()
            sessions = data.get("sessions", {})
            sessions = {
                sid: payload
                for sid, payload in sessions.items()
                if not self._is_expired(payload.get("created_at", ""))
            }
            data["sessions"] = sessions
            self._save(data)

    def save_session(self, session_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            data = self._load()
            data.setdefault("sessions", {})[session_id] = payload
            self._save(data)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._load()
            payload = data.get("sessions", {}).get(session_id)
            if not payload:
                return None
            if self._is_expired(payload.get("created_at", "")):
                data["sessions"].pop(session_id, None)
                self._save(data)
                return None
            return payload

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        with self._lock:
            data = self._load()
            sessions = data.get("sessions", {})
            payload = sessions.get(session_id)
            if not payload:
                return
            payload.update(updates)
            sessions[session_id] = payload
            data["sessions"] = sessions
            self._save(data)


def _escape(text: str) -> str:
    return html_lib.escape(text or "")


def build_menu_text(
    base_text: str,
    items: List[Dict[str, Any]],
    page: int,
    page_size: int,
    parse_mode: Optional[str],
    max_len: int = 3800
) -> str:
    if page < 1:
        page = 1
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * page_size
    end = min(total, start + page_size)

    lines = []
    mode = (parse_mode or "").lower()
    if mode == "html":
        lines.append("<b>详情索引</b>（点下方按钮查看）")
    else:
        lines.append("详情索引（点下方按钮查看）")
    for idx in range(start, end):
        item = items[idx]
        subject = (item.get("subject") or "").strip() or "(无主题)"
        sender = (item.get("from") or "").strip() or "unknown"
        prefix = f"{idx + 1}."
        if mode == "html":
            lines.append(f"{prefix} {_escape(subject)} — {_escape(sender)}")
        else:
            lines.append(f"{prefix} {subject} — {sender}")

    footer = f"页码: {page}/{total_pages}"
    lines.append(footer)
    separator = "\n" if base_text else ""
    combined = f"{base_text}{separator}" + "\n".join(lines)
    if len(combined) > max_len:
        notice = "日报内容过长，已折叠。"
        if mode == "html":
            combined = f"<b>{notice}</b>\n" + "\n".join(lines)
        else:
            combined = f"{notice}\n" + "\n".join(lines)
    return combined


def build_inline_keyboard(
    session_id: str,
    page: int,
    total_items: int,
    page_size: int,
    row_size: int = 4
) -> Dict[str, Any]:
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start = (page - 1) * page_size
    end = min(total_items, start + page_size)

    buttons: List[List[Dict[str, str]]] = []
    row: List[Dict[str, str]] = []
    for idx in range(start, end):
        number = str(idx + 1)
        row.append({
            "text": number,
            "callback_data": f"dg:{session_id}:{number}"
        })
        if len(row) >= row_size:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_row: List[Dict[str, str]] = []
    if page > 1:
        nav_row.append({
            "text": "上一页",
            "callback_data": f"dg_page:{session_id}:{page - 1}"
        })
    if page < total_pages:
        nav_row.append({
            "text": "下一页",
            "callback_data": f"dg_page:{session_id}:{page + 1}"
        })
    if nav_row:
        buttons.append(nav_row)

    return {"inline_keyboard": buttons}
