"""离线自测用的模拟数据：个股逐日数据随机生成，其后走和真实运行完全相同的 compute 流程
（个股 -> 行业汇总 -> 窗口/象限/排行）。股票代码用 X 开头的假代码，不会和真实股票混淆。"""
import numpy as np
import pandas as pd

import compute

# 行业名（新浪行业） -> (长期漂移, 近30日漂移)，用来构造四个象限
SPEC = {
    "金融行业": (+0.004, +0.004), "电力行业": (+0.003, +0.005), "煤炭行业": (+0.003, +0.002),
    "电子器件": (-0.004, +0.010), "汽车制造": (-0.003, +0.006), "电器行业": (-0.005, +0.004),
    "酿酒行业": (+0.005, -0.008), "医疗器械": (+0.004, -0.006), "生物制药": (+0.003, -0.007),
    "房地产": (-0.005, -0.006), "传媒娱乐": (-0.004, -0.005), "有色金属": (-0.003, -0.004),
    "电子信息": (-0.002, -0.010),
}


def make_result():
    rng = np.random.default_rng(7)
    dates = pd.bdate_range(end="2026-10-09", periods=260).strftime("%Y-%m-%d").tolist()
    imap, hist_rows, today_rows = {}, [], []
    for k, (ind, (long_d, short_d)) in enumerate(SPEC.items()):
        codes = [f"X{k:02d}{j:03d}" for j in range(8)]
        imap[ind] = codes
        for c in codes:
            for i, d in enumerate(dates):
                amount = rng.uniform(8e8, 25e8)
                drift = short_d if i >= len(dates) - 30 else long_d
                ratio = drift + rng.normal(0, 0.03)
                row = {"date": d, "code": c, "net": ratio * amount, "amount": amount}
                (today_rows if i == len(dates) - 1 else hist_rows).append(row)
    stock_hist = pd.DataFrame(hist_rows)
    today = pd.DataFrame(today_rows)
    stocks = today.assign(name=lambda x: "示例股" + x["code"].str[1:], pct_chg=rng.normal(0, 3, len(today)))[
        ["code", "name", "pct_chg", "net", "amount"]]

    history = compute.industry_history(stock_hist, imap)
    today_df = compute.industry_today(stocks, imap)
    result = compute.build_result(history, today_df, imap, stocks, stock_hist, mode="final",
                                  trade_date=dates[-1], updated_at="DEMO 模拟数据")
    # 模拟ETF份额：同向、背离，其余分别覆盖"无ETF/积累中"
    etf_rows = []
    for c, trend in (("512800", +0.002), ("512880", -0.003)):
        s = 1e9
        for d in dates[-30:]:
            s *= 1 + trend + rng.normal(0, 0.0005)
            etf_rows.append({"date": d, "code": c, "shares": s})
    etf_hist = pd.DataFrame(etf_rows)
    etf_map = {"金融行业": ["512800"], "电力行业": ["512880"], "电子器件": ["512480"]}
    return compute.attach_etf(result, etf_hist, etf_map)
