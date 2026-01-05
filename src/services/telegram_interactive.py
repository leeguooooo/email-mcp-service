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

    def _parse_created_at(self, created_at: str) -> datetime:
        try:
            return datetime.fromisoformat(created_at)
        except Exception:
            return datetime.min

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

    def get_latest_session_for_chat(
        self,
        chat_id: Optional[int]
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        with self._lock:
            data = self._load()
            sessions = data.get("sessions", {})
            candidates = []
            for session_id, payload in sessions.items():
                if self._is_expired(payload.get("created_at", "")):
                    continue
                if chat_id is not None and payload.get("chat_id") != chat_id:
                    continue
                candidates.append((session_id, payload))
            if not candidates:
                return None
            candidates.sort(key=lambda item: self._parse_created_at(item[1].get("created_at", "")))
            return candidates[-1]


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
    max_subject_len = 60
    for idx in range(start, end):
        item = items[idx]
        subject = (item.get("subject") or "").strip() or "(无主题)"
        if len(subject) > max_subject_len:
            subject = subject[: max_subject_len - 3] + "..."
        sender = (item.get("from") or "").strip()
        account = (item.get("account_id") or "").strip()
        prefix = f"{idx + 1}."
        if mode == "html":
            if account:
                suffix = f"<code>{_escape(account)}</code>"
            elif sender:
                suffix = _escape(sender)
            else:
                suffix = ""
            line = f"{prefix} {_escape(subject)}"
            if suffix:
                line = f"{line} — {suffix}"
            lines.append(line)
        else:
            suffix = account or sender
            if suffix:
                lines.append(f"{prefix} {subject} — {suffix}")
            else:
                lines.append(f"{prefix} {subject}")

    footer = f"页码: {page}/{total_pages}"
    lines.append(footer)
    separator = "\n\n" if base_text else ""
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
