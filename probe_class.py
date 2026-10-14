"""探测：证监会2012版（新浪 fenlei=2 中的一部分）覆盖情况 + 未覆盖个股的行业来源（只打印）：python run.py probe_class"""
import re
import time
from collections import Counter

import requests

import fetch
import fetch_sina

# 证监会2012版行业大类编号范围（按门类字母）
R2012 = {"A": (1, 5), "B": (6, 12), "C": (13, 43), "D": (44, 46), "E": (47, 50), "F": (51, 52), "G": (53, 60),
         "H": (61, 62), "I": (63, 65), "J": (66, 69), "K": (70, 70), "L": (71, 72), "M": (73, 75), "N": (76, 78),
         "O": (79, 81), "P": (82, 82), "Q": (83, 84), "R": (85, 88), "S": (89, 99)}


def is2012(cat):
    m = re.match(r"^hangye_Z([A-S])(\d\d)$", cat)
    if not m:
        return False
    lo, hi = R2012[m.group(1)]
    return lo <= int(m.group(2)) <= hi


def run():
    d = fetch_sina.get_json("MoneyFlow.ssl_bkzj_bk", {"page": 1, "num": 300, "sort": "netamount", "asc": 0, "fenlei": 2})
    bks = [(r["name"], r["category"]) for r in d if is2012(r["category"])]
    print(f"按2012版编号规则选出 {len(bks)} 个板块")
    st = fetch.fetch_stock_today()
    have = set(st["code"])
    mem = {}
    for name, cat in bks:
        mem[cat] = (name, fetch_sina.industry_cons(cat))
        time.sleep(0.15)
    cnt = Counter(c for _, v in mem.values() for c in v)
    cov = set(cnt) & have
    print(f"2012版覆盖 {len(cov)} 只，未覆盖 {len(have - cov)} 只；最大重复 {max(cnt.values())}；重复>1的股票 {sum(1 for v in cnt.values() if v > 1)} 只")
    miss = st[~st["code"].isin(cov)]
    print(f"未覆盖成交额占比 {float(miss['amount'].sum())/float(st['amount'].sum())*100:.1f}%；前缀 {dict(Counter(miss['code'].str[:3]).most_common(6))}")
    print("未覆盖示例:", "、".join(f"{r.name}({r.code})" for r in miss.sort_values('amount', ascending=False).head(40).itertuples()))
    print("各板块成分数:", "；".join(f"{n}:{len(v)}" for n, v in sorted(mem.values(), key=lambda x: -len(x[1]))[:60]))

    print("\n=== 抓取新浪个股资料页，看能否取到所属行业（8只未覆盖股）")
    for r in miss.sort_values("amount", ascending=False).head(8).itertuples():
        for url in (f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpOtherInfo/stockid/{r.code}/menu_num/2.phtml",
                    f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpInfo/stockid/{r.code}.phtml"):
            try:
                t = requests.get(url, headers=fetch_sina.UA, timeout=20)
                t.encoding = "gb2312"
                body = t.text
                hits = re.findall(r"[^<>\s]{0,12}行业[^<>\s]{0,24}", body)[:6]
                print(f"  {r.name}({r.code}) HTTP{t.status_code} 长度{len(body)} 行业相关: {hits}")
            except Exception as e:  # noqa: BLE001
                print(f"  {r.name}({r.code}) 失败 {type(e).__name__} {str(e)[:60]}")
            time.sleep(0.3)
    print("请求统计:", fetch_sina.STATS)
