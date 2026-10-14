"""全局配置。窗口、阈值、路径都在这里改。"""
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"

ETF_CSV = DATA / "etf_shares.csv"             # ETF份额每日快照（date, code, shares）
INDUSTRY_MAP_JSON = DATA / "industry_map.json"  # 行业 -> 成分股代码，每周刷新
STOCK_DIR = DATA / "stock_daily"              # 个股逐日（code, net, amount），每个交易日一个 csv.gz；行业历史由它按行业汇总得出
LATEST_JSON = DATA / "latest.json"            # 最新计算结果
ETF_MAP_JSON = ROOT / "etf_map.json"          # 行业 -> ETF代码（手工维护）

WINDOWS = [20, 60, 120, 250]
SHORT_WINDOW = 20          # 短期方向：近20日主力净流入占成交额比例
LONG_WINDOWS = [250, 120]  # 长期方向：优先250日，历史不足时退回120日
MIN_COVERAGE = 0.9         # 窗口内有效交易日 >= 窗口长度 * 该比例才计算
EPS = 0.0                  # 判定流入/流出的死区，0 表示严格按正负号

STOCK_TOPN = 3             # 每个行业、每个窗口展示的个股数量
STOCK_DEFAULT_WINDOW = 20  # 页面默认显示的窗口
RANK_TOPN = 3              # 各窗口资金流入/流出最多的行业数量
RANK_WINDOWS = WINDOWS   # 排行图与行业详情统一展示的周期
BACKFILL_DAYS = 320        # 回填个股历史的交易日数（新浪实测可回溯1000日以上）
MIN_STOCKS = 3000          # 当日个股数据少于此数视为抓取不完整，不写入历史
MAP_REFRESH_DAYS = 30       # 行业成分映射刷新周期
REQUEST_SLEEP = 0.4        # 逐行业请求之间的间隔（秒），降低被限流概率

QUADRANTS = {
    "q1": {"title": "短期流入、长期流入", "tag": "持续承接，可信度高", "stocks": True},
    "q2": {"title": "短期流入、长期流出", "tag": "疑似反弹承接或派发", "stocks": True},
    "q3": {"title": "短期流出、长期流入", "tag": "回调中资金未撤，值得跟踪", "stocks": True},
    "q4": {"title": "短期流出、长期流出", "tag": "持续撤离", "stocks": False},
}
