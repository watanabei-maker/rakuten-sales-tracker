# Rakuten Sales Tracker (Prototype)

楽天RMSの注文データを毎日自動取得して、CSVで蓄積するプロトタイプです。

## できること

- **OrderSearchAPI** で前日の注文番号を取得
- **GetOrderAPI** で注文明細(商品・金額・顧客)を取得
- 日次で次のCSVを生成 / 更新:
  - `data/orders_YYYY-MM-DD.csv` … 注文ヘッダ
  - `data/items_YYYY-MM-DD.csv`  … 商品明細
  - `data/daily_summary.csv`     … 日別売上サマリ(累積)
  - `data/item_ranking.csv`      … 商品別売上ランキング(全期間)

## 初期セットアップ

### 1. 楽天RMSでAPI利用開始

RMS Web Service の利用申込みを行い、**serviceSecret** と **licenseKey** を発行します。licenseKey は有効期限があるので運用時は要注意です。

### 2. GitHub Secrets に登録

リポジトリの Settings → Secrets and variables → Actions に以下を登録:

- `RAKUTEN_SERVICE_SECRET`
- `RAKUTEN_LICENSE_KEY`

### 3. ローカル実行(動作確認用)

```bash
pip install -r requirements.txt
export RAKUTEN_SERVICE_SECRET=xxxx
export RAKUTEN_LICENSE_KEY=yyyy
python src/fetch_orders.py
python src/aggregate.py
```

## 自動実行

`.github/workflows/daily.yml` で毎日 JST 06:00 に実行されます。手動で動かしたい時は GitHub Actions の画面から "Run workflow" でも起動できます。

## 注意点

- **licenseKey の更新**: 楽天の仕様で有効期限があるため、切れたら GitHub Secrets を更新してください。
- **GetOrderAPI のバージョン**: `rakuten_client.py` の `version` パラメータは楽天の最新仕様に合わせて確認してください。仕様変更でフィールド名が変わることがあります。
- **レート制限**: 大量注文がある店舗では `time.sleep` 値の調整が必要です。
- **タイムゾーン**: GitHub Actions は UTC で動くので、cron は UTC で書いています(JST 06:00 = UTC 21:00)。

## 次の発展

- Google スプレッドシートへの書き出し(`gspread` を追加)
- Amazon SP-API の追加(申請完了後)
- Looker Studio で可視化
