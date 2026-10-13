"""一次性回填个股历史（新浪，约320个交易日），首次部署必须先跑一次：
    python run.py backfill
约5000只股票，3个并发、每只约1秒，预计20~40分钟。可中断重跑：已完成的代码记录在
data/backfill_done.txt，下次自动跳过；失败的股票会在最后单线程再试一轮。
"""
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

import config
import fetch

DONE = config.DATA / "backfill_done.txt"
CHECKPOINT = 500
WORKERS = 3
SLEEP = 0.15


def _merge_into_daily(df):
    """把 (date, code, net, amount) 合并进按日文件；同一天同一只股票以新数据为准。"""
    config.STOCK_DIR.mkdir(parents=True, exist_ok=True)
    df = df.dropna(subset=["net"])
    for d, g in df.groupby("date"):
        p = config.STOCK_DIR / f"{d}.csv.gz"
        new = g[["code", "net", "amount"]]
        if p.exists():
            old = pd.read_csv(p, dtype={"code": str})
            if "amount" not in old.columns:
                old["amount"] = 0
            new = pd.concat([old, new], ignore_index=True)
        new = new.drop_duplicates("code", keep="last")
        new = new.assign(net=new["net"].round(0).astype("int64"),
                         amount=new["amount"].fillna(0).round(0).astype("int64"))
        new.to_csv(p, index=False, compression="gzip")


def _one(code):
    try:
        df = fetch.fetch_stock_hist(code)
        time.sleep(SLEEP)
        return code, df, None
    except Exception as e:  # noqa: BLE001
        return code, None, str(e)[:100]


def run():
    codes = fetch.fetch_stock_today()["code"].tolist()
    done = set(DONE.read_text().split()) if DONE.exists() else set()
    todo = [c for c in codes if c not in done]
    print(f"待回填 {len(todo)} 只，已完成 {len(done)} 只")
    buf, fresh, failed = [], [], []

    def flush(i):
        nonlocal buf, done, fresh
        if buf:
            _merge_into_daily(pd.concat(buf, ignore_index=True))
            done |= set(fresh)
            DONE.write_text("\n".join(sorted(done)))
            buf, fresh = [], []
        print(f"进度 {i}/{len(todo)}，失败 {len(failed)}")

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, (c, df, err) in enumerate(ex.map(_one, todo), 1):
            if err:
                failed.append(c)
            else:
                buf.append(df)
                fresh.append(c)
            if i % CHECKPOINT == 0:
                flush(i)
    flush(len(todo))

    if failed:                                  # 失败的单线程再试一轮
        print(f"重试失败的 {len(failed)} 只")
        retry_failed = []
        for c in failed:
            c, df, err = _one(c)
            if err:
                retry_failed.append(c)
                print(f"[warn] {c} 仍失败: {err}")
            else:
                buf.append(df)
                fresh.append(c)
            time.sleep(0.3)
        flush(len(todo))
        failed = retry_failed
    print(f"回填完成：成功 {len(done)} 只，最终失败 {len(failed)} 只（可再次运行 backfill 补齐）")
