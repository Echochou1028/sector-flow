"""窗口占比、四象限分类、个股TOP3、ETF验证。纯计算，不做网络请求。"""
import json

import pandas as pd

import config


def window_ratios(g):
    """单个行业的多窗口主力净流入占成交额比例。返回 {窗口: 比例或None}、有效天数。"""
    g = g.sort_values("date")
    out = {}
    for n in config.WINDOWS:
        if len(g) < n * config.MIN_COVERAGE:
            out[n] = None
            continue
        t = g.tail(n).dropna(subset=["net", "amount"])
        t = t[t["amount"] > 0]
        if len(t) < n * config.MIN_COVERAGE:
            out[n] = None
            continue
        out[n] = float(t["net"].sum() / t["amount"].sum())
    return out, len(g)


def _sign(x):
    if x is None:
        return None
    if x > config.EPS:
        return 1
    if x < -config.EPS:
        return -1
    return 0


def classify(ratios):
    """返回 (象限, 短期值, 长期值, 长期所用窗口)；数据不足返回 (None, ...)。"""
    short = ratios.get(config.SHORT_WINDOW)
    long_v, basis = None, None
    for w in config.LONG_WINDOWS:
        if ratios.get(w) is not None:
            long_v, basis = ratios[w], w
            break
    s, l = _sign(short), _sign(long_v)
    if s is None or l is None or s == 0 or l == 0:
        return None, short, long_v, basis
    q = {(1, 1): "q1", (1, -1): "q2", (-1, 1): "q3", (-1, -1): "q4"}[(s, l)]
    return q, short, long_v, basis


def window_nets(g):
    """行业各窗口主力净流入合计（亿元）。覆盖不足返回 None。"""
    g = g.sort_values("date")
    return {n: (None if len(g) < n * config.MIN_COVERAGE else round(float(g.tail(n)["net"].sum()) / 1e8, 2))
            for n in config.WINDOWS}


def window_pcts(price_g, pct_today):
    """行业各窗口涨幅（%）。price_g 为不含当日的收盘价序列；当日收盘价由昨收和今日涨跌幅推算，盘中/盘后通用。"""
    out = {n: None for n in config.WINDOWS}
    if price_g is None or len(price_g) == 0 or pct_today is None or pd.isna(pct_today):
        return out
    closes = price_g.sort_values("date")["close"].dropna().tolist()
    if not closes:
        return out
    today_close = closes[-1] * (1 + pct_today / 100.0)
    for n in config.WINDOWS:
        if len(closes) >= n:
            out[n] = round((today_close / closes[-n] - 1) * 100, 2)
    return out


def stock_window_sums(stock_hist, stocks_df, trade_date):
    """个股在各窗口内的主力净流入合计（元）。

    stock_hist: 已定稿的逐日数据（date, code, net）；stocks_df: 当日（暂计或定稿）个股数据。
    返回 (sums, cov)：sums[n] 是以代码为索引的 Series；cov[n] 是该窗口实际拥有的交易日数。
    """
    if stocks_df is None or stocks_df.empty:
        return {}, {}
    t = stocks_df[["code", "net"]].assign(date=trade_date)
    h = stock_hist[stock_hist["date"] != trade_date] if stock_hist is not None and len(stock_hist) else None
    full = pd.concat([h, t], ignore_index=True) if h is not None else t
    dates = sorted(full["date"].unique())
    sums, cov = {}, {}
    for n in config.WINDOWS:
        ds = dates[-n:]
        cov[n] = len(ds)
        sums[n] = full[full["date"].isin(ds)].groupby("code")["net"].sum()
    return sums, cov


def top_stocks(industry, imap, sums, cov, stocks_df):
    """行业内个股按各窗口主力净流入排名前N。返回 {"5": [...], ..., "cov": {...}}；无数据返回 None。"""
    codes = set(imap.get(industry, []))
    if not codes or not sums:
        return None
    info = stocks_df.set_index("code")
    out = {"cov": {str(n): cov[n] for n in config.WINDOWS}}
    for n in config.WINDOWS:
        s = sums[n]
        s = s[s.index.isin(codes) & s.index.isin(info.index)].dropna().sort_values(ascending=False).head(config.STOCK_TOPN)
        rows = []
        for code, v in s.items():
            pc = info.at[code, "pct_chg"]
            rows.append({"code": code, "name": str(info.at[code, "name"]), "net": round(float(v) / 1e8, 2),
                         "pct_chg": None if pd.isna(pc) else round(float(pc), 2)})
        out[str(n)] = rows
    return out


def build_result(history, today_df, imap, stocks_df, stock_hist, price_df, mode, trade_date, updated_at):
    """history: 已定稿的行业历史；today_df: 当日（暂计或定稿）行业数据；stock_hist: 个股逐日历史。"""
    sums, cov = stock_window_sums(stock_hist, stocks_df, trade_date)
    price_by = {}
    if price_df is not None and len(price_df):
        price_by = {k: v for k, v in price_df[price_df["date"] != trade_date].groupby("industry")}
    h = history[history["date"] != trade_date]
    t = today_df.assign(date=trade_date)[["date", "industry", "net", "amount"]]
    full = pd.concat([h, t], ignore_index=True)

    today_info = today_df.set_index("industry")
    quadrants = {k: [] for k in config.QUADRANTS}
    insufficient = []
    for ind, g in full.groupby("industry"):
        ratios, days = window_ratios(g)
        q, short, long_v, basis = classify(ratios)
        if q is None:
            insufficient.append(ind)
            continue
        info = today_info.loc[ind] if ind in today_info.index else None
        item = {
            "industry": ind,
            "ratios": {str(k): (None if v is None else round(v * 100, 2)) for k, v in ratios.items()},
            "short": round(short * 100, 2),
            "long": round(long_v * 100, 2),
            "long_basis": basis,
            "days": days,
            "nets": {str(k): v for k, v in window_nets(g).items()},
            "pcts": {str(k): v for k, v in window_pcts(
                price_by.get(ind), None if info is None else info["pct_chg"]).items()},
            "momentum": "加速" if (ratios.get(5) is not None and ratios.get(20) is not None
                                   and abs(ratios[5]) > abs(ratios[20])) else "减速",
            "today_net": None if info is None or pd.isna(info["net"]) else round(info["net"] / 1e8, 2),
            "pct_chg": None if info is None or pd.isna(info["pct_chg"]) else round(float(info["pct_chg"]), 2),
            "stocks": top_stocks(ind, imap, sums, cov, stocks_df) if config.QUADRANTS[q]["stocks"] else None,
            "etf": None,
        }
        quadrants[q].append(item)

    # 排序：q1/q2 短期流入越强越靠前；q3 长期流入越强越靠前；q4 短期流出越多越靠前
    quadrants["q1"].sort(key=lambda x: -x["short"])
    quadrants["q2"].sort(key=lambda x: -x["short"])
    quadrants["q3"].sort(key=lambda x: -x["long"])
    quadrants["q4"].sort(key=lambda x: x["short"])

    return {
        "mode": mode,
        "trade_date": trade_date,
        "updated_at": updated_at,
        "history_days": int(full.groupby("industry").size().max()) if len(full) else 0,
        "stock_default_window": config.STOCK_DEFAULT_WINDOW,
        "insufficient": sorted(insufficient),
        "quadrants": quadrants,
    }


def attach_etf(result, etf_hist, etf_map):
    """ETF验证：对比近20个交易日 ETF 份额变化方向与行业短期资金方向。T+1，历史积累不足时标记"积累中"。"""
    etf_hist = etf_hist.copy()
    if not etf_hist.empty:
        etf_hist["shares"] = pd.to_numeric(etf_hist["shares"], errors="coerce")
    for q, items in result["quadrants"].items():
        for it in items:
            codes = etf_map.get(it["industry"], [])
            if not codes:
                it["etf"] = {"status": "none", "text": "无对应ETF"}
                continue
            chgs = []
            for c in codes:
                s = etf_hist[etf_hist["code"] == str(c)].sort_values("date")
                if len(s) < config.SHORT_WINDOW + 1:
                    continue
                old, new = s["shares"].iloc[-(config.SHORT_WINDOW + 1)], s["shares"].iloc[-1]
                if pd.notna(old) and pd.notna(new) and old > 0:
                    chgs.append(new / old - 1)
            if not chgs:
                it["etf"] = {"status": "pending", "text": "ETF数据积累中"}
                continue
            chg = sum(chgs) / len(chgs)
            same = (chg > 0) == (it["short"] > 0)
            it["etf"] = {"status": "ok" if same else "diverge",
                         "text": f"ETF近{config.SHORT_WINDOW}日份额{chg * 100:+.1f}%，" + ("与资金同向" if same else "与资金背离"),
                         "chg": round(chg * 100, 2)}
    return result


def load_etf_map():
    p = config.ETF_MAP_JSON
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
