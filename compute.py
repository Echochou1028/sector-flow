"""窗口占比、四象限分类、个股TOP3、ETF验证。纯计算，不做网络请求。"""
import json

import pandas as pd

import config


def market_ratios(full):
    """全市场各窗口的主力净流入占成交额比例（所有行业合计）。
    新浪大单口径的"主力净流入"整体偏正（全市场合计并不为0），不扣除的话几乎所有行业都显示为流入，
    所以行业指标统一扣除全市场同期水平，只看相对强弱。"""
    d = full.groupby("date")[["net", "amount"]].sum().sort_index()
    out = {}
    for n in config.WINDOWS:
        t = d.tail(n)
        t = t[t["amount"] > 0]
        out[n] = float(t["net"].sum() / t["amount"].sum()) if len(t) and t["amount"].sum() > 0 else 0.0
    return out


def window_ratios(g, mk=None):
    """单个行业的多窗口主力净流入占成交额比例（mk 给定时扣除全市场同期比例）。返回 {窗口: 比例或None}、有效天数。"""
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
        out[n] = float(t["net"].sum() / t["amount"].sum()) - (mk.get(n, 0.0) if mk else 0.0)
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


def window_nets(g, mk=None):
    """行业各窗口主力净流入合计（亿元；mk 给定时扣除 全市场同期比例×本行业成交额）。覆盖不足返回 None。"""
    g = g.sort_values("date")
    out = {}
    for n in config.WINDOWS:
        if len(g) < n * config.MIN_COVERAGE:
            out[n] = None
            continue
        t = g.tail(n)
        v = float(t["net"].sum()) - (mk.get(n, 0.0) * float(t["amount"].sum()) if mk else 0.0)
        out[n] = round(v / 1e8, 2)
    return out


def _members(imap):
    return pd.DataFrame([(c, ind) for ind, cs in imap.items() if not ind.startswith("_") for c in cs],
                        columns=["code", "industry"]).drop_duplicates("code")


def industry_history(stock_hist, imap):
    """由个股逐日数据按行业汇总：返回 date, industry, net(元), amount(元)。
    amount 缺失（无法反推）的个股当日不计入成交额，影响很小。"""
    if stock_hist is None or stock_hist.empty:
        return pd.DataFrame(columns=["date", "industry", "net", "amount"])
    d = stock_hist.merge(_members(imap), on="code")
    d["amount"] = pd.to_numeric(d["amount"], errors="coerce").where(lambda x: x > 0)
    d["net"] = pd.to_numeric(d["net"], errors="coerce")
    return (d.groupby(["date", "industry"]).agg(net=("net", "sum"), amount=("amount", "sum"))
            .reset_index())


def industry_today(stocks_df, imap):
    """当日（暂计或定稿）个股数据按行业汇总：返回 industry, net, amount。"""
    d = stocks_df.merge(_members(imap), on="code")
    d["amount"] = d["amount"].where(d["amount"] > 0)
    return d.groupby("industry").agg(net=("net", "sum"), amount=("amount", "sum")).reset_index()


def rank_industries(per_ind, qmap):
    """各窗口资金流入/流出最多的行业前N。per_ind: {行业: (nets, ratios)}，窗口覆盖不足的行业不参与该窗口。"""
    out = {}
    for n in config.WINDOWS:
        rows = [(ind, nets[n], ratios.get(n)) for ind, (nets, ratios) in per_ind.items() if nets.get(n) is not None]
        pack = lambda r: {"industry": r[0], "net": r[1], "q": qmap.get(r[0]),
                          "ratio": None if r[2] is None else round(r[2] * 100, 2)}
        up = sorted([r for r in rows if r[1] > 0], key=lambda r: -r[1])[:config.RANK_TOPN]
        down = sorted([r for r in rows if r[1] < 0], key=lambda r: r[1])[:config.RANK_TOPN]
        out[str(n)] = {"in": [pack(r) for r in up], "out": [pack(r) for r in down]}
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


def build_result(history, today_df, imap, stocks_df, stock_hist, mode, trade_date, updated_at):
    """history: 已定稿的行业历史（由个股汇总）；today_df: 当日（暂计或定稿）行业数据；stock_hist: 个股逐日历史。"""
    sums, cov = stock_window_sums(stock_hist, stocks_df, trade_date)
    h = history[history["date"] != trade_date]
    t = today_df.assign(date=trade_date)[["date", "industry", "net", "amount"]]
    full = pd.concat([h, t], ignore_index=True)

    mk = market_ratios(full) if config.RELATIVE_TO_MARKET else None
    ta = float(today_df["amount"].sum())
    today_mk = float(today_df["net"].sum()) / ta if (config.RELATIVE_TO_MARKET and ta > 0) else 0.0
    today_info = today_df.set_index("industry")
    quadrants = {k: [] for k in config.QUADRANTS}
    insufficient = []
    per_ind, qmap = {}, {}
    for ind, g in full.groupby("industry"):
        ratios, days = window_ratios(g, mk)
        nets = window_nets(g, mk)
        per_ind[ind] = (nets, ratios)
        q, short, long_v, basis = classify(ratios)
        if q is None:
            insufficient.append(ind)
            continue
        qmap[ind] = q
        info = today_info.loc[ind] if ind in today_info.index else None
        item = {
            "industry": ind,
            "ratios": {str(k): (None if v is None else round(v * 100, 2)) for k, v in ratios.items()},
            "short": round(short * 100, 2),
            "long": round(long_v * 100, 2),
            "long_basis": basis,
            "days": days,
            "nets": {str(k): v for k, v in nets.items()},
            "today_net": None if info is None or pd.isna(info["net"]) else round(
                (info["net"] - today_mk * (0 if pd.isna(info["amount"]) else info["amount"])) / 1e8, 2),
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
        "windows": config.WINDOWS,
        "rank_windows": config.RANK_WINDOWS,
        "stock_default_window": config.STOCK_DEFAULT_WINDOW,
        "insufficient": sorted(insufficient),
        "quadrants": quadrants,
        "rank": rank_industries(per_ind, qmap),
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
