"""
集計結果をNotionデータベースに書き込むスクリプト。
"""

from __future__ import annotations

import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from notion_client import (
    NotionClient,
    NotionCredentials,
    date_prop,
    number_prop,
    rich_text_prop,
    select_prop,
    title_prop,
)

JST = timezone(timedelta(hours=9))
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def sync_daily_summary(client: NotionClient, db_id: str, channel: str) -> None:
    summary_path = DATA_DIR / "daily_summary.csv"
    if not summary_path.exists():
        print("[notion] daily_summary.csv が見つかりません。スキップ。")
        return

    existing = client.query_database(db_id)
    existing_by_key = {}
    for page in existing:
        props = page.get("properties", {})
        date_value = (props.get("Date", {}).get("date") or {}).get("start")
        ch_value = (props.get("Channel", {}).get("select") or {}).get("name")
        if date_value and ch_value:
            existing_by_key[(date_value, ch_value)] = page["id"]

    created, updated = 0, 0
    with summary_path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            date_str = row.get("date") or ""
            order_count = int(row.get("orderCount") or 0)
            total_sales = int(row.get("totalSales") or 0)
            avg_value = int(row.get("avgOrderValue") or 0)

            properties = {
                "Name": title_prop(f"{date_str} / {channel}"),
                "Date": date_prop(date_str),
                "Channel": select_prop(channel),
                "OrderCount": number_prop(order_count),
                "TotalSales": number_prop(total_sales),
                "AvgOrderValue": number_prop(avg_value),
            }

            key = (date_str, channel)
            if key in existing_by_key:
                client.update_page(existing_by_key[key], properties)
                updated += 1
            else:
                client.create_page(db_id, properties)
                created += 1

    print(f"[notion] daily_summary 同期完了: 新規 {created} 件 / 更新 {updated} 件")


def sync_item_ranking(client: NotionClient, db_id: str, channel: str) -> None:
    ranking_path = DATA_DIR / "item_ranking.csv"
    if not ranking_path.exists():
        print("[notion] item_ranking.csv が見つかりません。スキップ。")
        return

    existing = client.query_database(
        db_id,
        filter_obj={"property": "Channel", "select": {"equals": channel}},
    )
    for page in existing:
        client.archive_page(page["id"])
    if existing:
        print(f"[notion] 既存ランキング {len(existing)} 件をアーカイブ")

    today_str = datetime.now(JST).date().isoformat()
    inserted = 0
    with ranking_path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rank = int(row.get("rank") or 0)
            if rank > 50:
                break

            properties = {
                "Name": title_prop(row.get("itemName") or "(no name)"),
                "Channel": select_prop(channel),
                "ManageNumber": rich_text_prop(row.get("manageNumber") or ""),
                "TotalUnits": number_prop(int(row.get("totalUnits") or 0)),
                "TotalSales": number_prop(int(row.get("totalSales") or 0)),
                "Rank": number_prop(rank),
                "UpdatedAt": date_prop(today_str),
            }
            client.create_page(db_id, properties)
            inserted += 1

    print(f"[notion] item_ranking 同期完了: {inserted} 件挿入")


def main() -> int:
    channel = sys.argv[1] if len(sys.argv) > 1 else "Rakuten"
    print(f"[notion] チャネル: {channel}")

    daily_db_id = os.environ.get("NOTION_DAILY_DB_ID")
    ranking_db_id = os.environ.get("NOTION_RANKING_DB_ID")
    if not daily_db_id or not ranking_db_id:
        raise RuntimeError(
            "NOTION_DAILY_DB_ID と NOTION_RANKING_DB_ID を環境変数に設定してください"
        )

    creds = NotionCredentials.from_env()
    client = NotionClient(creds)

    sync_daily_summary(client, daily_db_id, channel)
    sync_item_ranking(client, ranking_db_id, channel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
