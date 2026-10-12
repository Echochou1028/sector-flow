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


def run2():
    """第二轮：逐个调用 AKShare 接口，打印它实际请求的网址与结果。"""
    import traceback

    import pandas as pd
    import requests.sessions as rs

    orig = rs.Session.send

    def logged(self, req, **kw):
        resp = orig(self, req, **kw)
        print(f"    ↳ {req.method} {req.url[:230]}")
        print(f"      UA={req.headers.get('User-Agent','')[:40]} → HTTP {resp.status_code} 长度{len(resp.text)} 开头{resp.text[:60]!r}")
        return resp

    rs.Session.send = logged
    import akshare as ak
    print("akshare 版本:", ak.__version__)

    def t(name, fn):
        print(f"\n=== {name}")
        try:
            df = fn()
            print(f"  成功 {df.shape} 列: {list(df.columns)[:14]}")
            print(df.head(2).to_string()[:400])
        except Exception as e:  # noqa: BLE001
            print(f"  失败 {type(e).__name__}: {str(e)[:150]}")

    t("AK 行业资金流排行(今日)", lambda: ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流"))
    t("AK 行业资金流历史(银行)", lambda: ak.stock_sector_fund_flow_hist(symbol="银行"))
    t("AK 行业板块日K(银行)", lambda: ak.stock_board_industry_hist_em(symbol="银行", period="日k", start_date="20260901", end_date="20261012", adjust=""))
    t("AK 个股资金流排行(今日)", lambda: ak.stock_individual_fund_flow_rank(indicator="今日"))
    t("AK 行业成分股(银行)", lambda: ak.stock_board_industry_cons_em(symbol="银行"))
    t("AK 交易日历", lambda: ak.tool_trade_date_hist_sina().tail(3))

    # 直连写法：不带头的 https，请求全部行业
    print("\n=== 直连 push2 行业资金流（https，无头，pz=100）")
    try:
        u = ("https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1&fltt=2&invt=2&fid=f62"
             "&fs=m:90+t:2&fields=f12,f14,f3,f62,f184")
        r = requests.get(u, timeout=20)
        d = r.json()["data"]
        print("  条数", d["total"], pd.DataFrame(d["diff"]).head(3).to_string())
    except Exception as e:  # noqa: BLE001
        print("  失败", type(e).__name__, str(e)[:150])
