"""连通性探测：在 GitHub Actions 上测试各数据源能否访问。用法：python run.py probe"""
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Referer": "https://data.eastmoney.com/"}

TESTS = [
    ("东财 push2 行业资金流(无头)", "https://push2.eastmoney.com/api/qt/clist/get?fid=f62&po=1&pz=5&pn=1&np=1&fltt=2&invt=2&fs=m:90+t:2&fields=f12,f14,f62", {}),
    ("东财 push2 行业资金流(浏览器头)", "https://push2.eastmoney.com/api/qt/clist/get?fid=f62&po=1&pz=5&pn=1&np=1&fltt=2&invt=2&fs=m:90+t:2&fields=f12,f14,f62", UA),
    ("东财 push2 http(非https)", "http://push2.eastmoney.com/api/qt/clist/get?fid=f62&po=1&pz=5&pn=1&np=1&fltt=2&invt=2&fs=m:90+t:2&fields=f12,f14,f62", UA),
    ("东财 push2his 历史", "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?lmt=3&klt=101&secid=1.600519&fields1=f1,f2,f3,f7&fields2=f51,f52,f53", UA),
    ("东财 数据中心", "https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_ORGHOLD_INDUSTRY&columns=ALL&pageSize=1", UA),
    ("新浪 交易日历", "https://finance.sina.com.cn/realstock/company/klc_td_sh.txt", UA),
    ("同花顺 行业资金流", "http://q.10jqka.com.cn/thshy/", UA),
]


def run():
    for name, url, headers in TESTS:
        t = time.time()
        try:
            r = requests.get(url, headers=headers, timeout=20)
            body = r.text[:80].replace("\n", " ")
            print(f"[{name}] HTTP {r.status_code} 长度{len(r.text)} {time.time()-t:.1f}s 开头: {body!r}")
        except Exception as e:  # noqa: BLE001
            print(f"[{name}] 失败 {type(e).__name__}: {str(e)[:120]}")
    try:
        print("出口IP:", requests.get("https://api.ipify.org", timeout=10).text)
    except Exception as e:  # noqa: BLE001
        print("出口IP 查询失败", e)
