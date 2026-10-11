"""离线自测用的模拟数据：走真实的 compute 流程，只是数据来源换成随机生成。"""
import numpy as np
import pandas as pd

import compute

# 行业名 -> (长期漂移, 近30日漂移)，用来构造四个象限
SPEC = {
    "银行": (+0.004, +0.004), "电力行业": (+0.003, +0.005), "煤炭行业": (+0.003, +0.002),
    "半导体": (-0.004, +0.010), "汽车整车": (-0.003, +0.006), "光伏设备": (-0.005, +0.004),
    "证券": (+0.005, -0.008), "酿酒行业": (+0.004, -0.006), "医疗器械": (+0.003, -0.007),
    "房地产开发": (-0.005, -0.006), "传媒": (-0.004, -0.005), "教育": (-0.003, -0.004),
    "软件开发": (-0.002, -0.010),
}


def make_result():
    rng = np.random.default_rng(7)
    dates = pd.bdate_range(end="2026-10-09", periods=260).strftime("%Y-%m-%d").tolist()
    rows, today_rows = [], []
    for ind, (long_d, short_d) in SPEC.items():
        for i, d in enumerate(dates):
            amount = rng.uniform(80e8, 200e8)
            drift = short_d if i >= len(dates) - 30 else long_d
            ratio = drift + rng.normal(0, 0.006)
            rows.append({"date": d, "industry": ind, "net": ratio * amount, "amount": amount})
    hist = pd.DataFrame(rows)
    last = hist[hist["date"] == dates[-1]]
    hist = hist[hist["date"] != dates[-1]]
    today = pd.DataFrame({
        "industry": last["industry"].values,
        "pct_chg": rng.normal(0.3, 1.2, len(last)),
        "net": last["net"].values, "amount": last["amount"].values})

    imap, srows, shist = {}, [], []
    for k, ind in enumerate(SPEC):
        codes = [f"{600000 + k * 100 + j:06d}" for j in range(8)]
        imap[ind] = codes
        for c in codes:
            # 每只股票有各自的"风格"，使不同窗口的TOP3会不一样
            bias_long, bias_short = rng.normal(0, 0.4e8), rng.normal(0, 1.2e8)
            for i, d in enumerate(dates[:-1]):
                shist.append({"date": d, "code": c,
                              "net": (bias_short if i >= len(dates) - 30 else bias_long) + rng.normal(0, 2e8)})
            srows.append({"code": c, "name": f"{ind[:2]}股{c[-3:]}", "pct_chg": rng.normal(0, 3),
                          "net": rng.normal(0, 3e8)})
    stocks = pd.DataFrame(srows)
    stock_hist = pd.DataFrame(shist)

    prows = []
    for ind, (long_d, short_d) in SPEC.items():
        px = 100.0
        for i, d in enumerate(dates[:-1]):
            px *= 1 + (short_d if i >= len(dates) - 30 else long_d) * 0.8 + rng.normal(0, 0.008)
            prows.append({"date": d, "industry": ind, "close": px})
    price_df = pd.DataFrame(prows)

    result = compute.build_result(hist, today, imap, stocks, stock_hist, price_df, mode="final",
                                  trade_date=dates[-1], updated_at="DEMO 模拟数据")
    # 模拟ETF份额：银行同向、证券背离、其余分别覆盖"无ETF/积累中"
    etf_rows = []
    for c, trend in (("512800", +0.002), ("512880", +0.003)):
        s = 1e9
        for d in dates[-30:]:
            s *= 1 + trend + rng.normal(0, 0.0005)
            etf_rows.append({"date": d, "code": c, "shares": s})
    etf_hist = pd.DataFrame(etf_rows)
    etf_map = {"银行": ["512800"], "证券": ["512880"], "半导体": ["512480"]}
    return compute.attach_etf(result, etf_hist, etf_map)
