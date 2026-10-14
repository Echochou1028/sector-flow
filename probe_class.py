"""探测：新浪个股资料页中的"所属行业（申万）"页面结构（只打印）：python run.py probe_class"""
import re
import time

import requests

import fetch_sina

URL = "https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpOtherInfo/stockid/{}/menu_num/2.phtml"


def run():
    for code in ("688825", "600938", "688072", "300750", "600519", "000001"):
        t = requests.get(URL.format(code), headers=fetch_sina.UA, timeout=20)
        t.encoding = "gb2312"
        html = t.text
        print(f"\n===== {code} HTTP{t.status_code} 长度{len(html)}")
        for key in ("所属行业板块", "备注：此为申万行业分类"):
            i = html.find(key)
            if i < 0:
                print(f"  [{key}] 未找到")
                continue
            seg = html[max(0, i - 200): i + 1200]
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", seg))
            txt = re.sub(r"(\| ?)+", "| ", txt)
            print(f"  [{key}] 附近文本: {txt[:700]}")
        time.sleep(0.5)
    # 速度测试：连续取 20 只
    t0 = time.time(); ok = 0
    for code in ("600000", "600004", "600006", "600007", "600008", "600009", "600010", "600011", "600012", "600015",
                 "000002", "000004", "000006", "000007", "000008", "000009", "000010", "000011", "000012", "000014"):
        try:
            requests.get(URL.format(code), headers=fetch_sina.UA, timeout=20); ok += 1
        except Exception:  # noqa: BLE001
            pass
    print(f"\n连续请求 20 只：成功 {ok}，用时 {time.time()-t0:.1f}s")
