"""
楽天RMS API クライアント

OrderSearchAPI と GetOrderAPI を呼び出すための薄いラッパー。
認証は serviceSecret と licenseKey を ":" でつないで Base64 エンコードし、
Authorization ヘッダーに "ESA <base64>" の形式で渡す。
"""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from typing import Any

import requests


ORDER_SEARCH_URL = "https://api.rms.rakuten.co.jp/es/2.0/order/searchOrder/"
GET_ORDER_URL = "https://api.rms.rakuten.co.jp/es/2.0/order/getOrder/"


@dataclass
class RakutenCredentials:
    """RMS API の認証情報。環境変数から読み込む。"""

    service_secret: str
    license_key: str

    @classmethod
    def from_env(cls) -> "RakutenCredentials":
        secret = os.environ.get("RAKUTEN_SERVICE_SECRET")
        license_key = os.environ.get("RAKUTEN_LICENSE_KEY")
        if not secret or not license_key:
            raise RuntimeError(
                "RAKUTEN_SERVICE_SECRET と RAKUTEN_LICENSE_KEY を環境変数に設定してください"
            )
        return cls(service_secret=secret.strip(), license_key=license_key.strip())

    def auth_header(self) -> str:
        token = f"{self.service_secret}:{self.license_key}".encode("utf-8")
        return "ESA " + base64.b64encode(token).decode("utf-8")


class RakutenRMSClient:
    """RMS APIの呼び出しに最低限必要なメソッドだけを実装したクライアント。"""

    def __init__(self, creds: RakutenCredentials, timeout: int = 30):
        self.creds = creds
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": creds.auth_header(),
                "Content-Type": "application/json; charset=utf-8",
            }
        )

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """共通のPOSTリクエスト。レート制限などで失敗したら指数バックオフで再試行。"""
        for attempt in range(3):
            response = self.session.post(url, json=payload, timeout=self.timeout)
            # 429(レート制限)や5xxは再試行
            if response.status_code in (429, 500, 502, 503, 504):
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        response.raise_for_status()
        return response.json()

    def search_orders(
        self,
        start_datetime: str,
        end_datetime: str,
        order_progress_list: list[int] | None = None,
    ) -> list[str]:
        """
        指定期間の注文番号の一覧を取得する。

        :param start_datetime: ISO8601形式 (例: "2026-04-24T00:00:00+0900")
        :param end_datetime:   ISO8601形式 (例: "2026-04-24T23:59:59+0900")
        :param order_progress_list: 注文ステータスで絞り込み(None なら全件)
                                    例: [100, 200, 300, 400, 500, 600, 700]
        :return: 注文番号(orderNumber)のリスト
        """
        order_numbers: list[str] = []
        request_page = 1

        while True:
            payload: dict[str, Any] = {
                "dateType": 1,  # 1=注文日, 3=発送日 など
                "startDatetime": start_datetime,
                "endDatetime": end_datetime,
                "PaginationRequestModel": {
                    "requestRecordsAmount": 1000,
                    "requestPage": request_page,
                },
            }
            if order_progress_list:
                payload["orderProgressList"] = order_progress_list

            data = self._post(ORDER_SEARCH_URL, payload)

            # メッセージのチェック
            common = data.get("MessageModelList", [])
            for msg in common:
                if msg.get("messageType") == "ERROR":
                    raise RuntimeError(f"OrderSearchAPI エラー: {msg}")

            order_numbers.extend(data.get("orderNumberList", []) or [])

            pagination = data.get("PaginationResponseModel", {}) or {}
            total_pages = pagination.get("totalPages", 1)
            if request_page >= total_pages:
                break
            request_page += 1

        return order_numbers

    def get_orders(self, order_numbers: list[str]) -> list[dict[str, Any]]:
        """
        注文番号から注文明細を取得する。
        GetOrderAPI は 1リクエストあたり最大100件まで。
        """
        results: list[dict[str, Any]] = []
        for i in range(0, len(order_numbers), 100):
            chunk = order_numbers[i : i + 100]
            payload = {
                "orderNumberList": chunk,
                "version": 7,  # GetOrderAPI のバージョン(楽天の最新仕様に合わせて要確認)
            }
            data = self._post(GET_ORDER_URL, payload)

            common = data.get("MessageModelList", [])
            for msg in common:
                if msg.get("messageType") == "ERROR":
                    raise RuntimeError(f"GetOrderAPI エラー: {msg}")

            results.extend(data.get("OrderModelList", []) or [])
            # 連続呼び出しのレート制限対策
            time.sleep(0.5)

        return results
