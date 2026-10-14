"""数据抓取层。主力资金数据走新浪（fetch_sina，直连），交易日历和ETF份额走 AKShare。

AKShare 的接口列名偶尔会改版，这里统一用 _pick 按关键词匹配列名，
匹配不到时抛出带列名清单的错误，方便排查。
"""
import datetime as dt
import json
import time

import pandas as pd

import config


def _retry(fn, *args, tries=3, wait=2.0, **kwargs):
    last = None
    for i in range(tries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(wait * (i + 1))
    raise last


def _pick(df, *keywords, required=True):
    """按关键词（全部包含）匹配列名。"""
    for col in df.columns:
        if all(k in str(col) for k in keywords):
            return col
    if required:
        raise KeyError(f"找不到列 {keywords}，实际列名: {list(df.columns)}")
    return None


def _amount(net, ratio_pct):
    """由净额和净占比(%)反推成交额；占比为0或缺失时返回 NaN。"""
    r = pd.to_numeric(ratio_pct, errors="coerce")
    n = pd.to_numeric(net, errors="coerce")
    return (n / (r / 100.0)).where(r.abs() > 1e-9).abs()


def is_trading_day(day=None):
    day = day or dt.date.today()
    try:
        import akshare as ak
        cal = _retry(ak.tool_trade_date_hist_sina)
        days = set(pd.to_datetime(cal["trade_date"]).dt.date)
        return day in days
    except Exception:  # noqa: BLE001
        return day.weekday() < 5  # 兜底：只排除周末


def fetch_stock_today():
    """沪深A股今日主力净流入（新浪，分页约12次请求）。返回 code, name, pct_chg, net, amount。"""
    import fetch_sina
    df = fetch_sina.stock_today()
    if len(df) < config.MIN_STOCKS:
        raise RuntimeError(f"个股当日数据只有 {len(df)} 只（少于 {config.MIN_STOCKS}），疑似抓取不完整，已中止")
    return df


def fetch_stock_hist(code):
    """单只个股逐日历史（约320个交易日），仅供一次性回填使用。返回 date, code, net, amount。"""
    import fetch_sina
    return fetch_sina.stock_hist(code, num=config.BACKFILL_DAYS)


def get_industry_map(codes=None, force=False, max_new=300):
    """申万一级行业 -> 成分股代码（28个）。数据来自新浪个股资料页，每只股票1次请求。
    缓存在 industry_map.json（含每只股票的编号）：日常只补抓新股（每次最多 max_new 只）；
    首次或 force=True（run.py industry）抓全部，约5500次请求、4线程约30分钟，中断后重跑自动续抓。"""
    import fetch_sina
    from concurrent.futures import ThreadPoolExecutor
    p = config.INDUSTRY_MAP_JSON
    cached = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    stocks = {} if force else dict(cached.get("_stocks", {}))
    if force and cached.get("_partial") and cached.get("_stocks"):   # 上次全量抓取被中断：接着抓
        stocks = dict(cached["_stocks"])
    codes = list(codes) if codes is not None else sorted(stocks)
    todo = [c for c in codes if c not in stocks]
    if stocks and not force and len(todo) > max_new:
        todo = todo[:max_new]
    print(f"[industry] 已有 {len(stocks)} 只，本次抓取 {len(todo)} 只")

    def save(partial):
        by = {}
        for c, (t, n) in stocks.items():
            nm = fetch_sina.SW1.get(str(t)[:2])
            if nm:
                by.setdefault(nm, []).append(c)
        out = {"_date": dt.date.today().isoformat(), "_partial": partial, "_stocks": stocks}
        out.update({k: sorted(v) for k, v in by.items()})
        p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return out

    def one(c):
        r = fetch_sina.stock_industry(c)
        time.sleep(0.15)
        return c, r
    n_err = 0
    if todo:
        with ThreadPoolExecutor(max_workers=4) as ex:
            for i, (c, r) in enumerate(ex.map(one, todo), 1):
                if r == "ERR":
                    n_err += 1
                else:
                    stocks[c] = [r[0], r[1]] if r else ["00", "无行业"]   # 页面没有行业的（如刚上市）记为无行业，不参与
                if i % 500 == 0:
                    save(True)
                    print(f"[industry] {i}/{len(todo)}")
        if n_err:
            print(f"[warn] 行业抓取失败 {n_err} 只（下次运行会自动补抓）")
    out = save(n_err > 0 and force)
    n_ind = sum(1 for k, v in out.items() if not k.startswith("_") and v)
    if n_ind < 20:
        raise RuntimeError(f"申万行业映射只取到 {n_ind} 个行业（应约28个），已中止；请先运行 industry 模式")
    return out


def fetch_etf_shares(codes, day=None):
    """沪深ETF当日份额快照。只保留 codes 里的ETF。

    沪市：fund_etf_scale_sse(date)；深市：fund_etf_scale_szse()（仅当前快照）。
    两个接口的列名不稳定，这里按关键词匹配，失败的一侧会被跳过并打印警告。
    """
    import akshare as ak
    day = day or dt.date.today()
    want = {str(c).zfill(6) for c in codes}
    rows = []
    for label, loader in (
        ("上交所", lambda: ak.fund_etf_scale_sse(date=day.strftime("%Y%m%d"))),
        ("深交所", lambda: ak.fund_etf_scale_szse()),
    ):
        try:
            df = _retry(loader)
            code_col = _pick(df, "代码")
            share_col = _pick(df, "份额", required=False) or _pick(df, "规模", "份", required=False)
            if share_col is None:
                raise KeyError(f"找不到份额列: {list(df.columns)}")
            for _, r in df.iterrows():
                c = str(r[code_col]).zfill(6)
                if c in want:
                    rows.append({"date": day.isoformat(), "code": c,
                                 "shares": pd.to_numeric(r[share_col], errors="coerce")})
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {label}ETF份额获取失败: {e}")
    return pd.DataFrame(rows, columns=["date", "code", "shares"])
