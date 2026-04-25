"""
Notion API クライアント

データベースへのレコード追加・更新・削除を担当する薄いラッパー。
- Notion API バージョン: 2022-06-28
- 認証: Bearer トークン (Internal Integration Secret)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


@dataclass
class NotionCredentials:
    """Notion API の認証情報。"""

    api_key: str

    @classmethod
    def from_env(cls) -> "NotionCredentials":
        api_key = os.environ.get("NOTION_API_KEY")
        if not api_key:
            raise RuntimeError("NOTION_API_KEY を環境変数に設定してください")
        return cls(api_key=api_key)


class NotionClient:
    def __init__(self, creds: NotionCredentials, timeout: int = 30):
        self.creds = creds
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {creds.api_key}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            }
        )

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{NOTION_API_BASE}{path}"
        for attempt in range(3):
            response = self.session.request(
                method, url, json=payload, timeout=self.timeout
            )
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            if not response.ok:
                try:
                    err = response.json()
                except Exception:
                    err = {"text": response.text}
                raise RuntimeError(
                    f"Notion API error {response.status_code}: {err}"
                )
            return response.json()
        response.raise_for_status()
        return response.json()

    def query_database(
        self,
        database_id: str,
        filter_obj: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        payload: dict[str, Any] = {}
        if filter_obj:
            payload["filter"] = filter_obj

        start_cursor = None
        while True:
            if start_cursor:
                payload["start_cursor"] = start_cursor
            data = self._request("POST", f"/databases/{database_id}/query", payload)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            start_cursor = data.get("next_cursor")
        return results

    def create_page(self, database_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        payload = {"parent": {"database_id": database_id}, "properties": properties}
        return self._request("POST", "/pages", payload)

    def update_page(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        payload = {"properties": properties}
        return self._request("PATCH", f"/pages/{page_id}", payload)

    def archive_page(self, page_id: str) -> dict[str, Any]:
        return self._request("PATCH", f"/pages/{page_id}", {"archived": True})


def title_prop(text: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": text}}]}


def rich_text_prop(text: str) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": text}}]}


def number_prop(value):
    return {"number": value}


def date_prop(iso_date: str) -> dict[str, Any]:
    return {"date": {"start": iso_date}}


def select_prop(name: str) -> dict[str, Any]:
    return {"select": {"name": name}}
