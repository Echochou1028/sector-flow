"""全局配置。窗口、阈值、路径都在这里改。"""
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"

HISTORY_CSV = DATA / "history.csv"            # 行业日度资金流（date, industry, net, amount）
ETF_CSV = DATA / "etf_shares.csv"             # ETF份额每日快照（date, code, shares）
INDUSTRY_MAP_JSON = DATA / "industry_map.json"  # 行业 -> 成分股代码，每周刷新
PRICE_CSV = DATA / "industry_price.csv"        # 行业日度收盘价（date, industry, close），用于各周期涨幅
STOCK_DIR = DATA / "stock_daily"              # 个股逐日主力净流入，每个交易日一个 csv.gz（追加式，不改写旧文件）
LATEST_JSON = DATA / "latest.json"            # 最新计算结果
ETF_MAP_JSON = ROOT / "etf_map.json"          # 行业 -> ETF代码（手工维护）

WINDOWS = [5, 20, 60, 120, 250]
SHORT_WINDOW = 20          # 短期方向：近20日主力净流入占成交额比例
LONG_WINDOWS = [250, 120]  # 长期方向：优先250日，历史不足时退回120日
MIN_COVERAGE = 0.9         # 窗口内有效交易日 >= 窗口长度 * 该比例才计算
EPS = 0.0                  # 判定流入/流出的死区，0 表示严格按正负号

STOCK_TOPN = 3             # 每个行业、每个窗口展示的个股数量
STOCK_DEFAULT_WINDOW = 20  # 页面默认显示的个股窗口
MAP_REFRESH_DAYS = 7       # 行业成分映射刷新周期
REQUEST_SLEEP = 0.4        # 逐行业请求之间的间隔（秒），降低被限流概率

QUADRANTS = {
    "q1": {"title": "短期流入、长期流入", "tag": "持续承接，可信度高", "stocks": True},
    "q2": {"title": "短期流入、长期流出", "tag": "疑似反弹承接或派发", "stocks": True},
    "q3": {"title": "短期流出、长期流入", "tag": "回调中资金未撤，值得跟踪", "stocks": True},
    "q4": {"title": "短期流出、长期流出", "tag": "持续撤离", "stocks": False},
}
