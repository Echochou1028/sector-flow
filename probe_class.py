"""探测可替代的行业分类来源（只打印，不写文件）：python run.py probe_class
测试：1) 新浪 ssl_bkzj_bk 的其他 fenlei 分类；2) 东方财富行业板块及成分股（需多次重试）。"""
import re
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
SINA = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
A = re.compile(r"^(sh6|sz0|sz3)\d{5}$")


def sina_fenlei():
    for f in range(0, 8):
        try:
            r = requests.get(SINA + "MoneyFlow.ssl_bkzj_bk", params={"page": 1, "num": 200, "sort": "netamount", "asc": 0, "bankuai": "", "shichang": "", "fenlei": f}, headers=UA, timeout=20)
            d = r.json()
            names = [x.get("name") for x in d][:6]
            print(f"  fenlei={f}: {len(d)} 个板块，示例 {names}")
        except Exception as e:  # noqa: BLE001
            print(f"  fenlei={f}: 失败 {type(e).__name__} {str(e)[:60]}")


def em_get(url, params, tries=6):
    last = ""
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers={**UA, "Referer": "https://quote.eastmoney.com/"}, timeout=20)
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__} {str(e)[:60]}"
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(last)


def eastmoney():
    base = "https://push2.eastmoney.com/api/qt/clist/get"
    try:
        d = em_get(base, {"pn": 1, "pz": 200, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3", "fs": "m:90+t:2", "fields": "f12,f14"})
        bks = d["data"]["diff"]
        print(f"  东财行业板块 {len(bks)} 个，示例 {[b['f14'] for b in bks[:6]]}")
    except Exception as e:  # noqa: BLE001
        print(f"  东财行业板块失败: {e}")
        return
    ok = fail = 0
    seen = set()
    t = time.time()
    for b in bks[:12]:
        try:
            c = em_get(base, {"pn": 1, "pz": 500, "po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3", "fs": "b:" + b["f12"], "fields": "f12,f14"})
            codes = [x["f12"] for x in c["data"]["diff"]]
            seen.update(codes); ok += 1
            print(f"    {b['f14']}: {len(codes)} 只")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"    {b['f14']}: 失败 {e}")
    print(f"  前12个板块 成功{ok} 失败{fail} 用时{time.time()-t:.0f}s，覆盖个股 {len(seen)}")


def run():
    print("=== 新浪其他分类")
    sina_fenlei()
    print("\n=== 东方财富行业板块 + 成分股")
    eastmoney()
