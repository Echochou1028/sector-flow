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


def run3():
    """第三轮：验证直连东财的每个接口。"""
    import traceback

    import fetch
    import fetch_em

    def step(name, fn):
        print(f"\n=== {name}")
        t = time.time()
        try:
            r = fn()
            print(f"  成功 {time.time()-t:.1f}s")
            return r
        except Exception as e:  # noqa: BLE001
            print(f"  失败 {type(e).__name__}: {str(e)[:300]}")
            return None

    ind = step("行业今日资金流列表", fetch.fetch_industry_today)
    if ind is not None:
        print(f"  行业数 {len(ind)}，成交额缺失 {int(ind['amount'].isna().sum())}")
        print(ind.head(5).to_string())
        print("  全部行业名:", "、".join(ind["industry"].tolist())[:3000])
    name = "银行" if ind is not None and "银行" in set(ind["industry"]) else (ind["industry"].iloc[0] if ind is not None else None)
    if name:
        h = step(f"行业资金流历史（{name}）", lambda: fetch.fetch_industry_hist(name))
        if h is not None:
            print(f"  {len(h)} 行，{h['date'].min()} ~ {h['date'].max()}")
            print(h.tail(3).to_string())
        pr = step(f"行业日K收盘价（{name}，430天）", lambda: fetch.fetch_industry_price(name, 430))
        if pr is not None:
            print(f"  {len(pr)} 行，{pr['date'].min()} ~ {pr['date'].max()}")
            print(pr.tail(3).to_string())
        c = step(f"行业成分股（{name}）", lambda: fetch.fetch_industry_cons(name))
        if c is not None:
            print(f"  {len(c)} 只，前5: {c[:5]}")
    st = step("全市场个股今日资金流（分页）", fetch.fetch_stock_today)
    if st is not None:
        print(f"  {len(st)} 只，净额缺失 {int(st['net'].isna().sum())}")
        print(st.sort_values('net', ascending=False).head(3).to_string())
    sh = step("个股历史资金流（600519）", lambda: fetch.fetch_stock_hist("600519"))
    if sh is not None:
        print(f"  {len(sh)} 行，{sh['date'].min()} ~ {sh['date'].max()}")
    print("\n请求统计:", fetch_em.STATS, "首选组合:", fetch_em._preferred)


def run4():
    """第四轮：数据源可行性——新浪资金流、同花顺、通达信(pytdx)。每项独立 try，互不影响。"""
    import subprocess
    import sys

    import pandas as pd

    def show(name, fn):
        print(f"\n=== {name}")
        t = time.time()
        try:
            r = fn()
            print(f"  成功 {time.time()-t:.1f}s")
            if isinstance(r, pd.DataFrame):
                print(f"  形状 {r.shape} 列 {list(r.columns)[:16]}")
                print(r.head(3).to_string()[:600])
            elif r is not None:
                print("  ", str(r)[:600])
        except Exception as e:  # noqa: BLE001
            print(f"  失败 {type(e).__name__}: {str(e)[:200]}")

    base = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    sina = [
        ("新浪 板块资金流 fenlei=0", base + "MoneyFlow.ssl_bkzj_bk?page=1&num=5&sort=netamount&asc=0&fenlei=0"),
        ("新浪 板块资金流 fenlei=1", base + "MoneyFlow.ssl_bkzj_bk?page=1&num=5&sort=netamount&asc=0&fenlei=1"),
        ("新浪 个股资金流排名", base + "MoneyFlow.ssl_bkzj_ssggzj?page=1&num=5&sort=netamount&asc=0&bankuai=&shichang="),
        ("新浪 个股资金流趋势(历史)", base + "MoneyFlow.ssl_qsfx_zjlrqs?page=1&num=5&sort=opendate&asc=0&daima=sh600519"),
        ("新浪 板块资金流趋势(历史)", base + "MoneyFlow.ssl_qsfx_lscjfb?page=1&num=5&sort=opendate&asc=0&bankuai=&shichang="),
    ]
    for name, url in sina:
        def f(url=url):
            r = requests.get(url, headers=UA, timeout=20)
            return f"HTTP {r.status_code} 长度{len(r.text)} 开头: {r.text[:450]!r}"
        show(name, f)

    import akshare as ak
    show("同花顺 行业资金流 即时", lambda: ak.stock_fund_flow_industry(symbol="即时"))
    show("同花顺 行业资金流 20日排行", lambda: ak.stock_fund_flow_industry(symbol="20日排行"))
    show("同花顺 个股资金流 即时", lambda: ak.stock_fund_flow_individual(symbol="即时"))

    def tdx():
        try:
            import pytdx  # noqa: F401
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pytdx"], check=True)
        from pytdx.hq import TdxHq_API
        api = TdxHq_API()
        out = []
        for ip, port in (("119.147.212.81", 7709), ("112.74.214.43", 7709), ("221.231.141.60", 7709), ("101.227.73.20", 7709)):
            try:
                if api.connect(ip, port, time_out=8):
                    out.append(f"{ip} 连接成功; 深圳证券数 {api.get_security_count(0)}")
                    tr = api.get_transaction_data(1, "600519", 0, 5)
                    out.append(f"  逐笔成交样例 {tr[:2] if tr else tr}")
                    api.disconnect()
                    break
                out.append(f"{ip} 连接失败")
            except Exception as e:  # noqa: BLE001
                out.append(f"{ip} 异常 {type(e).__name__} {str(e)[:60]}")
        return "\n   ".join(out)

    show("通达信 pytdx 连接与逐笔成交", tdx)

    show("东财 再试一次（本次出口IP）", lambda: requests.get(
        "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?lmt=3&klt=101&secid=1.600519&fields1=f1,f2,f3,f7&fields2=f51,f52,f53",
        timeout=20).text[:150])
    try:
        print("\n出口IP:", requests.get("https://api.ipify.org", timeout=10).text)
    except Exception as e:  # noqa: BLE001
        print("出口IP 查询失败", e)
