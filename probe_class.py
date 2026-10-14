"""探测新浪 fenlei=2（疑似证监会行业）分类的成分覆盖（只打印）：python run.py probe_class"""
import time
from collections import Counter

import fetch
import fetch_sina


def run():
    d = fetch_sina.get_json("MoneyFlow.ssl_bkzj_bk", {"page": 1, "num": 300, "sort": "netamount", "asc": 0, "fenlei": 2})
    bks = [(r["name"], r["category"]) for r in d]
    print(f"fenlei=2 共 {len(bks)} 个板块；category 示例 {[c for _, c in bks[:8]]}")
    st = fetch.fetch_stock_today()
    have = set(st["code"])
    mapping, bad = {}, 0
    for name, cat in bks:
        try:
            mapping[(name, cat)] = fetch_sina.industry_cons(cat)
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"  {name} 失败 {str(e)[:60]}")
        time.sleep(0.15)
    sizes = sorted(((len(v), k[0]) for k, v in mapping.items()), reverse=True)
    print(f"成功 {len(mapping)} 失败 {bad}；最大5个 {sizes[:5]}；最小5个 {sizes[-5:]}")
    cnt = Counter(c for v in mapping.values() for c in v)
    mapped = set(cnt)
    print(f"今日个股 {len(have)} 只，被覆盖 {len(have & mapped)} 只，未覆盖 {len(have - mapped)} 只")
    dist = Counter(cnt.values())
    print("每只股票所属板块数分布(板块数:股票数):", dict(sorted(dist.items())))
    print("成分数 >=10 的板块数:", sum(1 for v in mapping.values() if len(v) >= 10))
    print("全部板块(名称:成分数):")
    print("  " + "；".join(f"{k[0]}:{len(v)}" for k, v in sorted(mapping.items(), key=lambda x: -len(x[1]))))
    print("请求统计:", fetch_sina.STATS)
