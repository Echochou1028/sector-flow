"""东方财富数据直连（不经过 AKShare）。

背景：AKShare 1.19.1 的请求带 ut 参数和大量字段，在 GitHub Actions 上被东财网关返回 502，
最简参数的请求能成功，所以这里自己拼最简请求。网关偶尔 502/断连，所以每个请求会在
多种"域名/协议/请求头"组合间依次尝试，并记住上次成功的组合。
"""
import time

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
HOSTS = {
    "push2": ["push2.eastmoney.com", "push2delay.eastmoney.com"],
    "push2his": ["push2his.eastmoney.com"],
}
_preferred = {}   # 家族 -> 上次成功的 (host, scheme, headers_idx)
_session = requests.Session()
STATS = {"ok": 0, "fail": 0, "last_err": ""}


def _combos(family):
    out = []
    for host in HOSTS[family]:
        for scheme in ("https", "http"):
            for hi in (0, 1):
                out.append((host, scheme, hi))
    pref = _preferred.get(family)
    if pref in out:
        out.remove(pref)
        out.insert(0, pref)
    return out


def get_json(family, path, params, timeout=20):
    last = None
    for combo in _combos(family):
        host, scheme, hi = combo
        url = f"{scheme}://{host}{path}"
        try:
            r = _session.get(url, params=params, headers=(UA if hi else {}), timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            j = r.json()
            _preferred[family] = combo
            STATS["ok"] += 1
            return j
        except Exception as e:  # noqa: BLE001
            last = f"{host} {scheme} {'UA' if hi else '默认头'}: {type(e).__name__} {str(e)[:60]}"
            time.sleep(0.3)
    STATS["fail"] += 1
    STATS["last_err"] = last
    raise RuntimeError(f"东财请求失败 {path} 最后错误: {last}")


def _clist(fs, fields, fid="f62", pz=100, max_pages=200, sleep=0.12):
    """分页取 clist 列表，返回 diff 记录列表。"""
    rows, total, pn = [], None, 1
    while pn <= max_pages:
        j = get_json("push2", "/api/qt/clist/get", {
            "pn": pn, "pz": pz, "po": 1, "np": 1, "fltt": 2, "invt": 2,
            "fid": fid, "fs": fs, "fields": fields})
        d = j.get("data") or {}
        diff = d.get("diff") or []
        if isinstance(diff, dict):
            diff = list(diff.values())
        if total is None:
            total = d.get("total", 0)
        rows += diff
        if not diff or len(rows) >= total:
            break
        pn += 1
        time.sleep(sleep)
    return rows


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def industry_list():
    """行业板块今日资金流。返回 code, name, pct_chg, net, ratio(主力净占比%)。"""
    rows = _clist("m:90+t:2", "f12,f14,f3,f62,f184")
    return pd.DataFrame({
        "code": [r.get("f12") for r in rows], "name": [r.get("f14") for r in rows],
        "pct_chg": [_num(r.get("f3")) for r in rows], "net": [_num(r.get("f62")) for r in rows],
        "ratio": [_num(r.get("f184")) for r in rows]})


def board_cons(board_code):
    """板块成分股代码列表。"""
    rows = _clist(f"b:{board_code}+f:!50", "f12,f14", fid="f3")
    return [str(r["f12"]).zfill(6) for r in rows if r.get("f12")]


def stock_today():
    """全市场个股今日主力净流入。返回 code, name, pct_chg, net。"""
    fs = ("m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,"
          "m:1+t:23+f:!2,m:0+t:7+f:!2,m:1+t:3+f:!2")
    rows = _clist(fs, "f12,f14,f3,f62", sleep=0.1)
    return pd.DataFrame({
        "code": [str(r.get("f12")).zfill(6) for r in rows], "name": [r.get("f14") for r in rows],
        "pct_chg": [_num(r.get("f3")) for r in rows], "net": [_num(r.get("f62")) for r in rows]})


def flow_hist(secid, limit=0):
    """日度资金流历史（板块 secid 如 90.BK1283；个股如 1.600519 / 0.000001）。
    返回 date, net(主力净流入), ratio(主力净占比%), close, pct。"""
    j = get_json("push2his", "/api/qt/stock/fflow/daykline/get", {
        "lmt": limit, "klt": 101, "secid": secid,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63"})
    kl = ((j.get("data") or {}).get("klines")) or []
    recs = []
    for s in kl:
        p = s.split(",")
        if len(p) < 7:
            continue
        recs.append({"date": p[0], "net": _num(p[1]), "ratio": _num(p[6]),
                     "close": _num(p[11]) if len(p) > 11 else float("nan"),
                     "pct": _num(p[12]) if len(p) > 12 else float("nan")})
    return pd.DataFrame(recs, columns=["date", "net", "ratio", "close", "pct"])


def kline_close(secid, beg, end):
    """日K收盘价。beg/end 形如 20250101。返回 date, close。"""
    j = get_json("push2his", "/api/qt/stock/kline/get", {
        "secid": secid, "klt": 101, "fqt": 1, "beg": beg, "end": end,
        "fields1": "f1,f2,f3,f4,f5,f6", "fields2": "f51,f52,f53,f54,f55,f56,f57"})
    kl = ((j.get("data") or {}).get("klines")) or []
    recs = []
    for s in kl:
        p = s.split(",")
        if len(p) >= 3:
            recs.append({"date": p[0], "close": _num(p[2])})
    return pd.DataFrame(recs, columns=["date", "close"])


def stock_secid(code):
    code = str(code).zfill(6)
    return ("1." if code.startswith(("6", "9")) else "0.") + code
