"""数据抓取层（AKShare / 东方财富）。所有网络请求都集中在这里，便于替换数据源。

注意：AKShare 的接口列名偶尔会改版，这里统一用 _pick 按关键词匹配列名，
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


def fetch_industry_today():
    """全部行业今日主力资金流（盘中为暂计）。返回 industry, pct_chg, net, amount。"""
    import akshare as ak
    df = _retry(ak.stock_sector_fund_flow_rank, indicator="今日", sector_type="行业资金流")
    name = _pick(df, "名称")
    pct = _pick(df, "涨跌幅")
    net = _pick(df, "主力净流入", "净额")
    ratio = _pick(df, "主力净流入", "净占比")
    out = pd.DataFrame({
        "industry": df[name].astype(str),
        "pct_chg": pd.to_numeric(df[pct], errors="coerce"),
        "net": pd.to_numeric(df[net], errors="coerce"),
    })
    out["amount"] = _amount(df[net], df[ratio])
    return out


def fetch_industry_hist(industry):
    """单个行业的历史日度主力净流入（东方财富通常回溯约120个交易日）。"""
    import akshare as ak
    df = _retry(ak.stock_sector_fund_flow_hist, symbol=industry)
    d = _pick(df, "日期")
    net = _pick(df, "主力净流入", "净额")
    ratio = _pick(df, "主力净流入", "净占比")
    out = pd.DataFrame({
        "date": pd.to_datetime(df[d]).dt.strftime("%Y-%m-%d"),
        "industry": industry,
        "net": pd.to_numeric(df[net], errors="coerce"),
    })
    out["amount"] = _amount(df[net], df[ratio])
    return out


def fetch_industry_price(industry, days=430):
    """行业板块日K收盘价（东方财富行业板块指数）。days 为向前回溯的自然日数。"""
    import akshare as ak
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    df = _retry(ak.stock_board_industry_hist_em, symbol=industry, period="日k",
                start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"), adjust="")
    return pd.DataFrame({
        "date": pd.to_datetime(df[_pick(df, "日期")]).dt.strftime("%Y-%m-%d"),
        "industry": industry,
        "close": pd.to_numeric(df[_pick(df, "收盘")], errors="coerce"),
    })


def fetch_stock_today():
    """全市场个股今日主力净流入（一次请求）。返回 code, name, pct_chg, net。"""
    import akshare as ak
    df = _retry(ak.stock_individual_fund_flow_rank, indicator="今日")
    out = pd.DataFrame({
        "code": df[_pick(df, "代码")].astype(str).str.zfill(6),
        "name": df[_pick(df, "名称")].astype(str),
        "pct_chg": pd.to_numeric(df[_pick(df, "涨跌幅")], errors="coerce"),
        "net": pd.to_numeric(df[_pick(df, "主力净流入", "净额")], errors="coerce"),
    })
    return out


def fetch_stock_hist(code):
    """单只个股历史日度主力净流入（约120个交易日），仅供一次性回填使用。"""
    import akshare as ak
    market = "sh" if code.startswith("6") else ("bj" if code[0] in "489" else "sz")
    df = _retry(ak.stock_individual_fund_flow, stock=code, market=market, tries=2, wait=1.0)
    return pd.DataFrame({
        "date": pd.to_datetime(df[_pick(df, "日期")]).dt.strftime("%Y-%m-%d"),
        "code": code,
        "net": pd.to_numeric(df[_pick(df, "主力净流入", "净额")], errors="coerce"),
    })


def fetch_industry_cons(industry):
    import akshare as ak
    df = _retry(ak.stock_board_industry_cons_em, symbol=industry)
    return df[_pick(df, "代码")].astype(str).str.zfill(6).tolist()


def get_industry_map(industries, force=False):
    """行业 -> 成分股代码列表，缓存在 json，超过 MAP_REFRESH_DAYS 天才刷新。"""
    p = config.INDUSTRY_MAP_JSON
    cached = {}
    if p.exists():
        cached = json.loads(p.read_text(encoding="utf-8"))
        age = (dt.date.today() - dt.date.fromisoformat(cached.get("_date", "2000-01-01"))).days
        if not force and age < config.MAP_REFRESH_DAYS and all(i in cached for i in industries):
            return cached
    result = {"_date": dt.date.today().isoformat()}
    for ind in industries:
        try:
            result[ind] = fetch_industry_cons(ind)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 成分股获取失败 {ind}: {e}")
            result[ind] = cached.get(ind, [])  # 失败时沿用旧映射
        time.sleep(config.REQUEST_SLEEP)
    p.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


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
