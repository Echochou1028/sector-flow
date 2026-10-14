"""入口。
  intraday  盘中：抓今日个股暂计，叠加已存历史，生成页面（不写历史）
  final     盘后：保存当日个股数据（追加一个文件），生成定稿页面
  etf       晚间：记录ETF份额快照，刷新页面里的ETF验证（T+1）
  backfill  一次性回填个股历史（新浪，约20~30分钟；首次必须先跑，否则没有历史可算）
  probe     自检新浪数据层是否可用（只打印，不写文件）
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


def load_stock_hist(max_days=max(config.WINDOWS) + 5):
    """读取最近 max_days 个交易日的个股逐日文件：date, code, net, amount。"""
    files = sorted(config.STOCK_DIR.glob("*.csv.gz"))[-max_days:] if config.STOCK_DIR.exists() else []
    parts = []
    for f in files:
        d = pd.read_csv(f, dtype={"code": str})
        if "amount" not in d.columns:
            d["amount"] = float("nan")
        d["date"] = f.name[:10]
        parts.append(d[["date", "code", "net", "amount"]])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["date", "code", "net", "amount"])


def save_stock_day(stocks_df, trade_date):
    """保存当日个股（code, net, amount），每天一个文件，追加式。"""
    config.STOCK_DIR.mkdir(parents=True, exist_ok=True)
    d = stocks_df[["code", "net", "amount"]].dropna(subset=["net"]).copy()
    d["amount"] = d["amount"].fillna(0)
    d = d.assign(net=d["net"].round(0).astype("int64"), amount=d["amount"].round(0).astype("int64"))
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


def apply_override(imap, stocks_df):
    """industry_override.json：{"股票代码或名称": "申万一级行业名"}，用于修正分类滞后（转型/更名）的个股。"""
    p = config.ROOT / "industry_override.json" if hasattr(config, "ROOT") else None
    if p is None or not p.exists():
        return imap
    ov = {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    if not ov:
        return imap
    name2code = dict(zip(stocks_df["name"], stocks_df["code"]))
    imap = {k: (list(v) if not k.startswith("_") else v) for k, v in imap.items()}
    for key, target in ov.items():
        code = key if key in set(stocks_df["code"]) else name2code.get(key)
        if not code:
            print(f"[override] 找不到股票 {key}，已忽略"); continue
        if target not in imap or target.startswith("_"):
            imap[target] = []
        for ind, cs in imap.items():
            if not ind.startswith("_") and code in cs:
                cs.remove(code)
        imap[target].append(code)
        print(f"[override] {key}({code}) → {target}")
    return imap


def run_intraday_or_final(mode):
    import fetch
    today = now_bj().date()
    if not fetch.is_trading_day(today):
        print("非交易日，跳过")
        return
    trade_date = today.isoformat()
    stocks_df = fetch.fetch_stock_today()            # 不足 MIN_STOCKS 只会直接报错中止，避免写入残缺数据
    imap = apply_override(fetch.get_industry_map(stocks_df["code"].tolist()), stocks_df)
    if mode == "final":
        save_stock_day(stocks_df, trade_date)
    stock_hist = load_stock_hist()
    past = stock_hist[stock_hist["date"] != trade_date]
    if past["date"].nunique() < 20:
        print(f"[warn] 已累积历史只有 {past['date'].nunique()} 个交易日，请先手动运行一次 backfill 回填历史")
    history = compute.industry_history(past, imap)
    today_df = compute.industry_today(stocks_df, imap)
    result = compute.build_result(
        history, today_df, imap, stocks_df, stock_hist,
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
    ap.add_argument("mode", choices=["intraday", "final", "etf", "demo", "backfill", "probe", "industry"])
    m = ap.parse_args().mode
    if m == "industry":
        import fetch
        fetch.get_industry_map(fetch.fetch_stock_today()["code"].tolist(), force=True)
    elif m == "probe":
        import probe
        probe.run()
    elif m == "backfill":
        import backfill_stocks
        backfill_stocks.run()
    elif m == "etf":
        run_etf()
    elif m == "demo":
        run_demo()
    else:
        run_intraday_or_final(m)
