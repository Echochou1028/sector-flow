"""一次性回填个股历史（约120个交易日），让20/60/120日窗口不用等累积。

约5000只股票逐只请求，按每只0.3秒间隔加请求耗时，预计1~2小时，只需在 Actions 里手动跑一次：
    python run.py backfill
可中断重跑：已完成的代码记录在 data/backfill_done.txt，下次自动跳过。
"""
import time

import pandas as pd

import config
import fetch

DONE = config.DATA / "backfill_done.txt"
CHECKPOINT = 400


def _merge_into_daily(df):
    config.STOCK_DIR.mkdir(parents=True, exist_ok=True)
    df = df.dropna(subset=["net"])
    for d, g in df.groupby("date"):
        p = config.STOCK_DIR / f"{d}.csv.gz"
        new = g[["code", "net"]]
        if p.exists():
            old = pd.read_csv(p, dtype={"code": str})
            new = pd.concat([old, new], ignore_index=True)
        new = new.drop_duplicates("code", keep="last")
        new = new.assign(net=new["net"].round(0).astype("int64"))
        new.to_csv(p, index=False, compression="gzip")


def run():
    codes = fetch.fetch_stock_today()["code"].tolist()
    done = set(DONE.read_text().split()) if DONE.exists() else set()
    todo = [c for c in codes if c not in done]
    print(f"待回填 {len(todo)} 只，已完成 {len(done)} 只")
    buf, fresh = [], []
    for i, c in enumerate(todo, 1):
        try:
            buf.append(fetch.fetch_stock_hist(c))
            fresh.append(c)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {c} 失败: {e}")
        time.sleep(config.REQUEST_SLEEP)
        if i % CHECKPOINT == 0 or i == len(todo):
            if buf:
                _merge_into_daily(pd.concat(buf, ignore_index=True))
                DONE.write_text("\n".join(sorted(done | set(fresh))))
                buf = []
            print(f"进度 {i}/{len(todo)}")
    done |= set(fresh)
    DONE.write_text("\n".join(sorted(done)))
