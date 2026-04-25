"""
昨日分の注文を取得して CSV に保存するメインスクリプト。

GitHub Actions から毎日呼ばれる想定。
- data/orders_YYYY-MM-DD.csv  : 注文ヘッダ単位
- data/items_YYYY-MM-DD.csv   : 商品明細単位 (注文1件に複数行)
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rakuten_client import RakutenCredentials, RakutenRMSClient


JST = timezone(timedelta(hours=9))
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def yesterday_range_jst() -> tuple[str, str, str]:
    """昨日の 00:00:00 から 23:59:59 (JST) の範囲を返す。"""
    today = datetime.now(JST).date()
    yesterday = today - timedelta(days=1)
    start = datetime.combine(yesterday, datetime.min.time(), tzinfo=JST)
    end = datetime.combine(yesterday, datetime.max.time(), tzinfo=JST).replace(
        microsecond=0
    )
    fmt = "%Y-%m-%dT%H:%M:%S%z"
    # RMS は +0900 形式を要求するので末尾の : を除く
    start_str = start.strftime(fmt)
    end_str = end.strftime(fmt)
    return start_str, end_str, yesterday.isoformat()


def write_orders_csv(orders: list[dict[str, Any]], path: Path) -> None:
    """注文ヘッダを CSV に書き出す。"""
    fields = [
        "orderNumber",
        "orderDatetime",
        "totalPrice",
        "goodsPrice",
        "postagePrice",
        "deliveryPrice",
        "orderProgress",
        "buyerName",
        "itemCount",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for o in orders:
            buyer = (o.get("OrdererModel") or {}).get("familyName", "") + (
                o.get("OrdererModel") or {}
            ).get("firstName", "")
            items = o.get("PackageModelList") or []
            item_count = sum(
                len(p.get("ItemModelList") or []) for p in items
            )
            writer.writerow(
                {
                    "orderNumber": o.get("orderNumber"),
                    "orderDatetime": o.get("orderDatetime"),
                    "totalPrice": o.get("totalPrice"),
                    "goodsPrice": o.get("goodsPrice"),
                    "postagePrice": o.get("postagePrice"),
                    "deliveryPrice": o.get("deliveryPrice"),
                    "orderProgress": o.get("orderProgress"),
                    "buyerName": buyer,
                    "itemCount": item_count,
                }
            )


def write_items_csv(orders: list[dict[str, Any]], path: Path) -> None:
    """注文に含まれる商品を 1行ずつ CSV に書き出す。"""
    fields = [
        "orderNumber",
        "orderDatetime",
        "itemNumber",
        "manageNumber",
        "itemName",
        "price",
        "units",
        "subtotal",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for o in orders:
            for pkg in o.get("PackageModelList") or []:
                for item in pkg.get("ItemModelList") or []:
                    price = item.get("price") or 0
                    units = item.get("units") or 0
                    writer.writerow(
                        {
                            "orderNumber": o.get("orderNumber"),
                            "orderDatetime": o.get("orderDatetime"),
                            "itemNumber": item.get("itemNumber"),
                            "manageNumber": item.get("manageNumber"),
                            "itemName": item.get("itemName"),
                            "price": price,
                            "units": units,
                            "subtotal": price * units,
                        }
                    )


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    start, end, date_str = yesterday_range_jst()
    print(f"[fetch] 取得期間: {start} 〜 {end}")

    creds = RakutenCredentials.from_env()
    client = RakutenRMSClient(creds)

    # 1. 注文番号一覧を取得 (キャンセル除いた全ステータス)
    order_numbers = client.search_orders(
        start_datetime=start,
        end_datetime=end,
        order_progress_list=[100, 200, 300, 400, 500, 600, 700],
    )
    print(f"[fetch] 注文件数: {len(order_numbers)}")

    if not order_numbers:
        print("[fetch] 対象注文なし。空ファイルだけ作成します。")
        write_orders_csv([], DATA_DIR / f"orders_{date_str}.csv")
        write_items_csv([], DATA_DIR / f"items_{date_str}.csv")
        return 0

    # 2. 注文明細を取得
    orders = client.get_orders(order_numbers)
    print(f"[fetch] 明細取得完了: {len(orders)} 件")

    # 3. CSV 書き出し
    write_orders_csv(orders, DATA_DIR / f"orders_{date_str}.csv")
    write_items_csv(orders, DATA_DIR / f"items_{date_str}.csv")
    print(f"[fetch] 保存先: {DATA_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
