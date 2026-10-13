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


def get_industry_map(force=False):
    """行业 -> 成分股代码列表（新浪行业，48个），缓存在 json，超过 MAP_REFRESH_DAYS 天才刷新。"""
    import fetch_sina
    p = config.INDUSTRY_MAP_JSON
    cached = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if cached and not force:
        age = (dt.date.today() - dt.date.fromisoformat(cached.get("_date", "2000-01-01"))).days
        if age < config.MAP_REFRESH_DAYS:
            return cached
    result = {"_date": dt.date.today().isoformat()}
    for name, cat in fetch_sina.industry_list():
        try:
            result[name] = fetch_sina.industry_cons(cat)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 成分股获取失败 {name}: {e}")
            result[name] = cached.get(name, [])   # 失败时沿用旧映射
        time.sleep(0.3)
    if sum(1 for k, v in result.items() if not k.startswith("_") and v) < 30:
        raise RuntimeError("行业成分映射取到的行业不足30个，已中止")
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
