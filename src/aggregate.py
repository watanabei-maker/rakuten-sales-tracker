"""
日次の集計スクリプト。

data/orders_*.csv と data/items_*.csv を読み込み、
- daily_summary.csv : 日別の売上サマリ (累積追記)
- item_ranking.csv  : 商品別の売上ランキング (全期間累積で再生成)
を作る。
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SUMMARY_PATH = DATA_DIR / "daily_summary.csv"
RANKING_PATH = DATA_DIR / "item_ranking.csv"


def yesterday_str() -> str:
    return (datetime.now(JST).date() - timedelta(days=1)).isoformat()


def update_daily_summary(date_str: str) -> None:
    """指定日の orders_*.csv を読んで daily_summary.csv に1行追記する。"""
    orders_csv = DATA_DIR / f"orders_{date_str}.csv"
    if not orders_csv.exists():
        print(f"[aggregate] {orders_csv} が見つかりません。スキップ。")
        return

    total_sales = 0
    total_orders = 0
    with orders_csv.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            total_orders += 1
            try:
                total_sales += int(row["totalPrice"] or 0)
            except ValueError:
                pass

    avg = total_sales // total_orders if total_orders else 0

    # 既存の summary を読み、同じ日付の行は置き換える
    rows: list[dict[str, str]] = []
    if SUMMARY_PATH.exists():
        with SUMMARY_PATH.open(encoding="utf-8-sig") as f:
            rows = [r for r in csv.DictReader(f) if r["date"] != date_str]

    rows.append(
        {
            "date": date_str,
            "orderCount": str(total_orders),
            "totalSales": str(total_sales),
            "avgOrderValue": str(avg),
        }
    )
    rows.sort(key=lambda r: r["date"])

    with SUMMARY_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["date", "orderCount", "totalSales", "avgOrderValue"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"[aggregate] daily_summary を更新: {date_str} 売上 {total_sales:,}円 / {total_orders}件")


def rebuild_item_ranking() -> None:
    """全 items_*.csv を集計して商品別ランキングを再生成する。"""
    sales_by_item: dict[str, dict[str, int | str]] = defaultdict(
        lambda: {"itemName": "", "units": 0, "subtotal": 0}
    )

    for items_csv in sorted(DATA_DIR.glob("items_*.csv")):
        with items_csv.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                key = row.get("manageNumber") or row.get("itemNumber") or ""
                if not key:
                    continue
                entry = sales_by_item[key]
                entry["itemName"] = row.get("itemName", "")
                try:
                    entry["units"] = int(entry["units"]) + int(row.get("units") or 0)
                    entry["subtotal"] = int(entry["subtotal"]) + int(
                        row.get("subtotal") or 0
                    )
                except ValueError:
                    pass

    ranked = sorted(
        sales_by_item.items(),
        key=lambda kv: int(kv[1]["subtotal"]),
        reverse=True,
    )

    with RANKING_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "manageNumber", "itemName", "totalUnits", "totalSales"])
        for rank, (key, v) in enumerate(ranked, start=1):
            writer.writerow([rank, key, v["itemName"], v["units"], v["subtotal"]])
    print(f"[aggregate] item_ranking を再生成: {len(ranked)} 商品")


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    date_str = sys.argv[1] if len(sys.argv) > 1 else yesterday_str()
    update_daily_summary(date_str)
    rebuild_item_ranking()
    return 0


if __name__ == "__main__":
    sys.exit(main())
