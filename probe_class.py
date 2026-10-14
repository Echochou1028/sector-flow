"""探测新浪 fenlei=2 的分类版本结构（只打印）：python run.py probe_class"""
import re
import time
from collections import Counter, defaultdict

import fetch
import fetch_sina


def run():
    d = fetch_sina.get_json("MoneyFlow.ssl_bkzj_bk", {"page": 1, "num": 300, "sort": "netamount", "asc": 0, "fenlei": 2})
    bks = [(r["name"], r["category"]) for r in d]
    st = fetch.fetch_stock_today()
    have = set(st["code"])
    mem = {}
    for name, cat in bks:
        mem[cat] = (name, fetch_sina.industry_cons(cat))
        time.sleep(0.15)
    print("=== 全部板块 代码|名称|成分数")
    for cat, (name, v) in sorted(mem.items()):
        print(f"{cat}|{name}|{len(v)}")
    # 按代码形态分组
    groups = defaultdict(list)
    for cat in mem:
        suf = cat.replace("hangye_", "")
        shape = re.sub(r"[A-Z]", "A", re.sub(r"\d", "9", suf))
        groups[shape].append(cat)
    print("\n=== 按代码形态分组（A=字母 9=数字）")
    for shape, cats in sorted(groups.items()):
        cnt = Counter(c for k in cats for c in mem[k][1])
        nz = [k for k in cats if mem[k][1]]
        print(f"形态 {shape}: 板块{len(cats)}个(非空{len(nz)})，覆盖个股{len(set(cnt) & have)}只，最大重复{max(cnt.values()) if cnt else 0}，每股平均所属{(sum(cnt.values())/len(cnt)) if cnt else 0:.2f}个")
    # ---- 未归属个股分析（466只问题）
    allc = {c for _, v in mem.values() for c in v}
    miss = st[~st["code"].isin(allc)]
    print(f"\n=== 未被 fenlei=2 任何板块覆盖的个股：{len(miss)} 只")
    print("代码前缀分布:", dict(Counter(miss["code"].str[:3]).most_common(8)))
    print("名称含ST/退/N/C开头:", int(miss["name"].str.contains(r"ST|退|^N|^C", regex=True).sum()))
    print("成交额合计(亿):", round(float(miss["amount"].sum()) / 1e8, 1), "占全市场", f"{float(miss['amount'].sum())/float(st['amount'].sum())*100:.1f}%")
    print("示例:", "、".join(f"{r.name}({r.code})" for r in miss.head(30).itertuples()))
    old = {}
    for n, cat in fetch_sina.industry_list():
        for c in fetch_sina.industry_cons(cat):
            old[c] = n
        time.sleep(0.15)
    got = miss[miss["code"].isin(old)]
    print(f"其中被新浪48行业覆盖的 {len(got)} 只，两套都没有的 {len(miss) - len(got)} 只")
    print("两套都没有的示例:", "、".join(f"{r.name}({r.code})" for r in miss[~miss["code"].isin(old)].head(30).itertuples()))
    print("请求统计:", fetch_sina.STATS)
