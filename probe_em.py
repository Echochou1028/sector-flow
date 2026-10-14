"""探测东方财富 F10 资料接口能否取到每只股票的"东财行业"和"证监会行业"（只打印）：python run.py probe_em"""
import json
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Referer": "https://emweb.securities.eastmoney.com/"}
URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"


def call(params, tries=5):
    last = ""
    for i in range(tries):
        t = time.time()
        try:
            r = requests.get(URL, params=params, headers=UA, timeout=25)
            j = r.json()
            return j, i + 1, time.time() - t
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__} {str(e)[:60]}"
            time.sleep(1.5 * (i + 1))
    return {"__err": last}, tries, 0


def base(**kw):
    p = {"reportName": "RPT_F10_BASIC_ORGINFO", "columns": "ALL", "quoteColumns": "", "sortTypes": "1", "sortColumns": "SECURITY_CODE",
         "source": "HSF10", "client": "PC", "pageNumber": 1, "pageSize": 1}
    p.update(kw)
    return p


def run():
    print("=== 1) 单只股票（山子高科 000981）全部字段中和行业相关的")
    j, n, dt = call(base(filter='(SECURITY_CODE="000981")'))
    if "__err" in j:
        print("  失败", j["__err"]); return
    rows = (j.get("result") or {}).get("data") or []
    print(f"  尝试{n}次 {dt:.1f}s 行数 {len(rows)}；success={j.get('success')} message={j.get('message')}")
    if rows:
        r = rows[0]
        print("  字段名:", list(r.keys())[:60])
        for k, v in r.items():
            if any(x in k.upper() for x in ("INDUSTRY", "EM2016", "BOARD", "CSRC", "NAME")):
                print(f"    {k}: {str(v)[:80]}")

    print("\n=== 2) 全市场分页（不带过滤，每页500）")
    tot = 0
    got = {}
    for pn in range(1, 14):
        j, n, dt = call(base(pageNumber=pn, pageSize=500))
        if "__err" in j:
            print(f"  第{pn}页 失败: {j['__err']}"); continue
        res = j.get("result") or {}
        rows = res.get("data") or []
        for r in rows:
            got[r.get("SECURITY_CODE")] = (r.get("EM2016"), r.get("INDUSTRYCSRC1"))
        print(f"  第{pn}页 尝试{n}次 {dt:.1f}s 行数{len(rows)} 总页数{res.get('pages')} 总数{res.get('count')}")
        if len(rows) < 500:
            break
    print(f"  合计取到 {len(got)} 只")
    for code, name in (("000981", "山子高科"), ("300604", "长川科技"), ("000628", "先导基电"), ("688072", "拓荆科技"), ("600519", "贵州茅台")):
        print(f"  {name}({code}): 东财行业={got.get(code, ('无', '无'))[0]} | 证监会行业={got.get(code, ('无', '无'))[1]}")
    em1 = {}
    for v in got.values():
        if v[0]:
            k = str(v[0]).split("-")[0]
            em1[k] = em1.get(k, 0) + 1
    print(f"  东财行业一级共 {len(em1)} 个:", dict(sorted(em1.items(), key=lambda x: -x[1])))
    csrc2 = {}
    for v in got.values():
        if v[1]:
            csrc2[v[1]] = csrc2.get(v[1], 0) + 1
    print(f"  证监会行业（门类-大类）共 {len(csrc2)} 个；最大10个:", sorted(csrc2.items(), key=lambda x: -x[1])[:10])
    print(f"  缺东财行业的 {sum(1 for v in got.values() if not v[0])} 只；缺证监会行业的 {sum(1 for v in got.values() if not v[1])} 只")
