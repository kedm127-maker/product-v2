#!/usr/bin/env python3
"""每日抓取證交所快照。

兩個用途：
  1. data/latest.json  — 前端在直接呼叫 API 失敗時的備援來源
  2. data/YYYY-MM-DD.json — 累積歷史，之後才算得出「本益比自身歷史分位」

證交所只給當日快照，沒有歷史端點。沒跑到的那一天補不回來。
"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://openapi.twse.com.tw/v1"
ENDPOINTS = {
    "val": "/exchangeReport/BWIBBU_ALL",
    "day": "/exchangeReport/STOCK_DAY_ALL",
    "rev": "/opendata/t187ap05_L",
}
OUT = "data"
KEEP_SLIM_DAYS = 400

TPE = timezone(timedelta(hours=8))


def fetch(path, retries=3):
    url = BASE + path
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "tw-sector-rank/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            if i == retries - 1:
                raise
            print(f"  retry {i+1}: {exc}", file=sys.stderr)
            time.sleep(5 * (i + 1))


def main():
    os.makedirs(OUT, exist_ok=True)
    today = datetime.now(TPE).strftime("%Y-%m-%d")

    snap = {"captured_at": datetime.now(TPE).isoformat(timespec="seconds")}
    for key, path in ENDPOINTS.items():
        print(f"fetch {path}")
        snap[key] = fetch(path)
        print(f"  {len(snap[key])} rows")

    if len(snap["val"]) < 100 or len(snap["day"]) < 100:
        print("回傳筆數異常偏低，可能是非交易日或來源異常，不覆寫 latest.json", file=sys.stderr)
        return 0

    with open(os.path.join(OUT, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, separators=(",", ":"))

    slim = [
        {
            "c": r.get("Code"),
            "pe": r.get("PEratio"),
            "pb": r.get("PBratio"),
            "dy": r.get("DividendYield"),
        }
        for r in snap["val"]
    ]
    with open(os.path.join(OUT, f"{today}.json"), "w", encoding="utf-8") as f:
        json.dump({"date": today, "ratios": slim}, f, ensure_ascii=False, separators=(",", ":"))

    cutoff = (datetime.now(TPE) - timedelta(days=KEEP_SLIM_DAYS)).strftime("%Y-%m-%d")
    for fn in os.listdir(OUT):
        stem = fn[:-5]
        if fn.endswith(".json") and len(stem) == 10 and stem < cutoff:
            os.remove(os.path.join(OUT, fn))

    print(f"wrote latest.json + {today}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
