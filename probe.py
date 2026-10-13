"""自检新浪数据层（只打印，不写文件）：python run.py probe"""
import time

import fetch
import fetch_sina


def _step(name, fn):
    print(f"\n=== {name}")
    t = time.time()
    try:
        r = fn()
        print(f"  成功 {time.time()-t:.1f}s")
        return r
    except Exception as e:  # noqa: BLE001
        print(f"  失败 {type(e).__name__}: {str(e)[:300]}")
        return None


def run():
    st = _step("全市场个股今日主力净流入", fetch.fetch_stock_today)
    if st is not None:
        print(f"  共 {len(st)} 只；成交额缺失 {int(st['amount'].isna().sum())}；净额缺失 {int(st['net'].isna().sum())}")
        print(st.sort_values("net", ascending=False).head(3).to_string())

    inds = _step("新浪行业列表", fetch_sina.industry_list)
    if inds:
        print(f"  {len(inds)} 个行业")

    mapping = {}

    def cons_all():
        for name, cat in inds or []:
            codes = fetch_sina.industry_cons(cat)
            mapping[name] = codes
            raw, total = fetch_sina.industry_cons.last_raw, fetch_sina.industry_cons.last_total
            flag = "" if total is None or raw == total else f"  ← 取到{raw}行，板块总数{total}，不一致！"
            print(f"  {name:6s} A股成分 {len(codes):4d}{flag}")
            time.sleep(0.2)
    _step("行业成分股（全部）", cons_all)
    if mapping and st is not None:
        mapped = {c for v in mapping.values() for c in v}
        have = set(st["code"])
        print(f"\n  今日个股 {len(have)} 只，其中已归入新浪行业 {len(have & mapped)} 只，"
              f"未归类 {len(have - mapped)} 只；同一股票出现在多个行业的重复数 {sum(len(v) for v in mapping.values()) - len(mapped)}")

    for code in ("600519", "000001", "300750", "688981"):
        h = _step(f"个股历史 {code}（320日）", lambda c=code: fetch.fetch_stock_hist(c))
        if h is not None and len(h):
            print(f"  {len(h)} 行，{h['date'].min()} ~ {h['date'].max()}；成交额无法反推 {int(h['amount'].isna().sum())} 行")
            print(h.head(2).to_string())
    print("\n请求统计:", fetch_sina.STATS)
