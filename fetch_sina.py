"""新浪财经数据直连（不经过 AKShare）。

为什么用新浪：东方财富的接口对 GitHub 机房 IP 时通时断；新浪实测稳定（40 次连续请求 0 失败）。
新浪给出的"主力净流入"字段是 r0_net，口径与东财不同，页面上统一写"主力净流入（新浪口径）"。

用到的接口（均为 vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/ 下）：
  MoneyFlow.ssl_bkzj_ssggzj   个股资金流排名（当日；含基金/ETF，需按代码过滤）
  MoneyFlow.ssl_qsfx_zjlrqs   个股资金流逐日历史（num=300 可回溯约300个交易日，实测）
  MoneyFlow.ssl_bkzj_bk       板块资金流排名（fenlei=0 为行业，共48个）
  Market_Center.getHQNodeData 板块成分股
"""
import re
import time

import pandas as pd
import requests

BASE = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
A_SHARE = re.compile(r"^(sh6|sz0|sz3)\d{5}$")      # 沪深A股（含科创板、创业板），排除基金/债券/指数/北交所
STATS = {"ok": 0, "fail": 0, "last_err": ""}
_session = requests.Session()
_session.headers.update(UA)


def get_json(path, params, tries=5, timeout=25):
    """带指数退避的请求；返回解析后的 JSON。新浪出错时会返回 {"__ERROR":...}，也按失败处理。"""
    last = None
    for i in range(tries):
        try:
            r = _session.get(BASE + path, params=params, timeout=timeout)
            r.raise_for_status()
            j = r.json()
            if isinstance(j, dict) and "__ERROR" in j:
                raise RuntimeError(f"新浪返回错误 {j}")
            STATS["ok"] += 1
            return j
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__} {str(e)[:80]}"
            time.sleep(min(1.0 * (2 ** i), 12))
    STATS["fail"] += 1
    STATS["last_err"] = last
    raise RuntimeError(f"新浪请求失败 {path} {params.get('daima', '')}（重试{tries}次）: {last}")


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def stock_today(page_size=500, max_pages=40, sleep=0.3):
    """全市场沪深A股今日主力净流入。返回 code, name, pct_chg(%), net(元), amount(元)。"""
    rows, seen = [], set()
    for pn in range(1, max_pages + 1):
        d = get_json("MoneyFlow.ssl_bkzj_ssggzj", {
            "page": pn, "num": page_size, "sort": "netamount", "asc": 0, "bankuai": "", "shichang": ""})
        if not d:
            break
        for r in d:
            sym = r.get("symbol", "")
            if A_SHARE.match(sym) and sym not in seen:
                seen.add(sym)
                rows.append(r)
        time.sleep(sleep)
    return pd.DataFrame({
        "code": [r["symbol"][2:] for r in rows],
        "name": [r.get("name") for r in rows],
        "pct_chg": [_f(r.get("changeratio")) * 100 for r in rows],
        "net": [_f(r.get("r0_net")) for r in rows],
        "amount": [_f(r.get("amount")) for r in rows],
    })


def _derive_amount(net, ratio):
    """成交额 = 净额 ÷ 净占比；占比接近0时无法反推，返回 NaN。"""
    return net / ratio if ratio == ratio and abs(ratio) > 1e-4 else float("nan")


def stock_hist(code, num=300):
    """单只个股逐日主力净流入。返回 date, code, net(元), amount(元，由净额÷净占比反推)。"""
    prefix = "sh" if str(code).startswith("6") else "sz"
    d = get_json("MoneyFlow.ssl_qsfx_zjlrqs", {
        "page": 1, "num": num, "sort": "opendate", "asc": 0, "daima": prefix + str(code).zfill(6)})
    recs = []
    for r in d:
        net = _f(r.get("r0_net"))
        amount = _derive_amount(net, _f(r.get("r0_ratio")))
        if amount != amount:   # 主力占比太小时，退回用总净额与总占比反推
            amount = _derive_amount(_f(r.get("netamount")), _f(r.get("ratioamount")))
        recs.append({"date": r.get("opendate"), "code": str(code).zfill(6), "net": net, "amount": amount})
    return pd.DataFrame(recs, columns=["date", "code", "net", "amount"])


def industry_list():
    """新浪行业板块列表（共48个）。返回 [(名称, 板块代码)]。"""
    d = get_json("MoneyFlow.ssl_bkzj_bk", {"page": 1, "num": 200, "sort": "netamount", "asc": 0, "fenlei": 0})
    return [(r["name"], r["category"]) for r in d]


def industry_cons(category, page_size=100, max_pages=20):
    """板块成分股（6位代码，只保留沪深A股）。"""
    total = None
    try:
        total = int(get_json("Market_Center.getHQNodeStockCount", {"node": category}))
    except Exception:  # noqa: BLE001
        pass
    codes, raw = [], 0
    for pn in range(1, max_pages + 1):
        d = get_json("Market_Center.getHQNodeData", {
            "page": pn, "num": page_size, "sort": "symbol", "asc": 1, "node": category, "symbol": "", "_s_r_a": "page"})
        if not d:
            break
        raw += len(d)
        codes += [r["symbol"][2:] for r in d if A_SHARE.match(r.get("symbol", ""))]
        if (total is not None and raw >= total) or (total is None and len(d) < page_size):
            break
        time.sleep(0.2)
    industry_cons.last_raw, industry_cons.last_total = raw, total   # 供自检：取到的行数应等于板块总数
    return sorted(set(codes))
