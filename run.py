"""入口。三种模式：
  intraday  盘中：抓今日暂计 + 个股，叠加已存历史，生成页面（不写历史）
  final     盘后：刷新各行业历史并落盘，生成定稿页面
  etf       晚间：记录ETF份额快照，刷新页面里的ETF验证（T+1）
  backfill  一次性回填个股历史（约1~2小时，只需手动跑一次）
  demo      用随机模拟数据跑通全流程（离线自测，不联网）
"""
import argparse
import datetime as dt
import json
import time

import pandas as pd

import build_site
import compute
import config

BJ = dt.timezone(dt.timedelta(hours=8))


def now_bj():
    return dt.datetime.now(BJ)


def load_history():
    if config.HISTORY_CSV.exists():
        return pd.read_csv(config.HISTORY_CSV, dtype={"industry": str})
    return pd.DataFrame(columns=["date", "industry", "net", "amount"])


def save_history(df):
    df = df.drop_duplicates(["date", "industry"], keep="last").sort_values(["industry", "date"])
    df.to_csv(config.HISTORY_CSV, index=False)


def load_price():
    if config.PRICE_CSV.exists():
        return pd.read_csv(config.PRICE_CSV, dtype={"industry": str})
    return pd.DataFrame(columns=["date", "industry", "close"])


def save_price(df):
    df.drop_duplicates(["date", "industry"], keep="last").sort_values(["industry", "date"]).to_csv(config.PRICE_CSV, index=False)


def load_stock_hist(max_days=max(config.WINDOWS)):
    """读取最近 max_days 个交易日的个股逐日文件。"""
    files = sorted(config.STOCK_DIR.glob("*.csv.gz"))[-max_days:] if config.STOCK_DIR.exists() else []
    parts = []
    for f in files:
        d = pd.read_csv(f, dtype={"code": str})
        d["date"] = f.name[:10]
        parts.append(d[["date", "code", "net"]])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["date", "code", "net"])


def save_stock_day(stocks_df, trade_date):
    """保存当日个股主力净流入（每天一个文件，追加式）。"""
    config.STOCK_DIR.mkdir(parents=True, exist_ok=True)
    d = stocks_df[["code", "net"]].dropna()
    d = d.assign(net=d["net"].round(0).astype("int64"))
    d.to_csv(config.STOCK_DIR / f"{trade_date}.csv.gz", index=False, compression="gzip")


def load_etf_hist():
    if config.ETF_CSV.exists():
        return pd.read_csv(config.ETF_CSV, dtype={"code": str})
    return pd.DataFrame(columns=["date", "code", "shares"])


def finish(result):
    etf_map = {k: v for k, v in compute.load_etf_map().items() if not k.startswith("_")}
    result = compute.attach_etf(result, load_etf_hist(), etf_map)
    config.LATEST_JSON.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    build_site.render(result)
    n = {k: len(v) for k, v in result["quadrants"].items()}
    print(f"[ok] {result['mode']} {result['trade_date']} 象限数量 {n} 数据不足 {len(result['insufficient'])}")


def run_intraday_or_final(mode):
    import fetch
    today = now_bj().date()
    if not fetch.is_trading_day(today):
        print("非交易日，跳过")
        return
    trade_date = today.isoformat()
    today_df = fetch.fetch_industry_today()
    history = load_history()

    if mode == "final":
        parts = [history]
        for ind in today_df["industry"]:
            try:
                parts.append(fetch.fetch_industry_hist(ind))
            except Exception as e:  # noqa: BLE001
                print(f"[warn] 历史获取失败 {ind}: {e}")
            time.sleep(config.REQUEST_SLEEP)
        history = pd.concat(parts, ignore_index=True)
        # 当日行：以历史接口为准；接口还没出当日数据时用 rank 接口的值兜底
        have_today = set(history.loc[history["date"] == trade_date, "industry"])
        fallback = today_df.assign(date=trade_date)[["date", "industry", "net", "amount"]]
        history = pd.concat([history, fallback[~fallback["industry"].isin(have_today)]], ignore_index=True)
        save_history(history)
        history = load_history()

    price_df = load_price()
    if mode == "final":
        # 首次回溯约430个自然日；之后只补最近25天
        full_hist = len(price_df) and price_df.groupby("industry").size().min() >= 250
        parts = [price_df]
        for ind in today_df["industry"]:
            try:
                parts.append(fetch.fetch_industry_price(ind, days=25 if full_hist else 430))
            except Exception as e:  # noqa: BLE001
                print(f"[warn] 行业价格获取失败 {ind}: {e}")
            time.sleep(config.REQUEST_SLEEP)
        price_df = pd.concat(parts, ignore_index=True)
        save_price(price_df)
        price_df = load_price()

    try:
        stocks_df = fetch.fetch_stock_today()
        imap = fetch.get_industry_map(list(today_df["industry"]))
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 个股/成分映射获取失败，个股TOP3留空: {e}")
        stocks_df, imap = None, {}

    if mode == "final" and stocks_df is not None:
        save_stock_day(stocks_df, trade_date)
    result = compute.build_result(
        history, today_df, imap, stocks_df, load_stock_hist(), price_df,
        mode="final" if mode == "final" else "intraday",
        trade_date=trade_date, updated_at=now_bj().strftime("%Y-%m-%d %H:%M"))
    finish(result)


def run_etf():
    import fetch
    etf_map = {k: v for k, v in compute.load_etf_map().items() if not k.startswith("_")}
    codes = sorted({c for v in etf_map.values() for c in v})
    if not codes:
        print("etf_map.json 为空，跳过")
        return
    snap = fetch.fetch_etf_shares(codes, now_bj().date())
    hist = pd.concat([load_etf_hist(), snap], ignore_index=True).drop_duplicates(["date", "code"], keep="last")
    hist.to_csv(config.ETF_CSV, index=False)
    if not config.LATEST_JSON.exists():
        print("尚无 latest.json，先跑一次 final")
        return
    result = json.loads(config.LATEST_JSON.read_text(encoding="utf-8"))
    finish(result)


def run_demo():
    import demo_data
    result = demo_data.make_result()
    config.LATEST_JSON.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    build_site.render(result)
    n = {k: len(v) for k, v in result["quadrants"].items()}
    print(f"[demo] 象限数量 {n}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["intraday", "final", "etf", "demo", "backfill", "probe", "probe2"])
    m = ap.parse_args().mode
    if m == "probe":
        import probe
        probe.run()
    elif m == "probe2":
        import probe
        probe.run2()
    elif m == "backfill":
        import backfill_stocks
        backfill_stocks.run()
    elif m == "etf":
        run_etf()
    elif m == "demo":
        run_demo()
    else:
        run_intraday_or_final(m)
