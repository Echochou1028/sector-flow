"""东方财富 F10 公司资料（批量）：每只股票的"东财行业"和"证监会行业"。
接口 datacenter.eastmoney.com/securities/api/data/v1/get，reportName=RPT_F10_BASIC_ORGINFO，
每页500条、全市场约50页（含新三板等非A股，只保留沪深A股），每页约1秒，实测在 GitHub 机器上稳定。
字段：BOARD_NAME_LEVEL=东财行业（如 汽车-汽车零部件-底盘与发动机系统），INDUSTRYCSRC1=证监会行业（如 制造业-汽车制造业）。
"""
import re
import time

import pandas as pd
import requests

URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Referer": "https://emweb.securities.eastmoney.com/"}
A_CODE = re.compile(r"^(60|68|00|30)\d{4}$")
_s = requests.Session()
_s.headers.update(HEADERS)


def _page(pn, tries=6):
    last = ""
    for i in range(tries):
        try:
            r = _s.get(URL, params={"reportName": "RPT_F10_BASIC_ORGINFO", "columns": "ALL", "quoteColumns": "",
                                    "sortTypes": "1", "sortColumns": "SECURITY_CODE", "source": "HSF10", "client": "PC",
                                    "pageNumber": pn, "pageSize": 500}, timeout=30)
            j = r.json()
            if not j.get("success"):
                raise RuntimeError(f"success=false {j.get('message')}")
            res = j.get("result") or {}
            return res.get("data") or [], int(res.get("pages") or 0)
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__} {str(e)[:80]}"
            time.sleep(min(1.5 * (i + 1), 10))
    raise RuntimeError(f"东财F10第{pn}页取不到（重试{tries}次）: {last}")


def fetch_basic_info(max_pages=80):
    """返回 DataFrame：code, name, board（东财行业，3级用'-'连接）, csrc（证监会行业 门类-大类）。只含沪深A股。"""
    rows, pages, pn = [], None, 1
    while pn <= (pages or max_pages) and pn <= max_pages:
        data, pages = _page(pn)
        if not data:
            break
        for r in data:
            c = str(r.get("SECURITY_CODE") or "")
            if A_CODE.match(c):
                rows.append((c, r.get("SECURITY_NAME_ABBR"), r.get("BOARD_NAME_LEVEL") or "", r.get("INDUSTRYCSRC1") or ""))
        pn += 1
        time.sleep(0.2)
    df = pd.DataFrame(rows, columns=["code", "name", "board", "csrc"]).drop_duplicates("code")
    if len(df) < 3000:
        raise RuntimeError(f"东财F10只取到 {len(df)} 只A股（应约5400），疑似不完整，已中止")
    return df


# 东财少数股票（约140只）的行业仍是旧版一级名称，这里并入新版一级，避免出现只有几只股票的"小行业"
ALIAS1 = {"信息技术": "计算机", "互联网": "计算机", "电气设备": "电力设备", "电子设备": "电子", "建筑": "建筑装饰",
          "交运设备": "汽车", "文化传媒": "传媒", "休闲、生活及专业服务": "社会服务", "化石能源": "石油石化"}


def level_name(text, scheme, level):
    """从'a-b-c'形式的行业文本取指定层级的名称；缺失返回 None。
    东财行业 level=1/2/3：取前 level 段，用'-'连接；证监会 level=1 门类、2 大类（只取大类名）。"""
    if not text:
        return None
    parts = [p.strip() for p in str(text).split("-") if p.strip()]
    if not parts:
        return None
    if scheme == "csrc":
        return parts[0] if level <= 1 else (parts[1] if len(parts) > 1 else parts[0])
    if parts[0] == "化石能源" and len(parts) > 1 and "煤" in parts[1]:
        parts[0] = "煤炭"
    else:
        parts[0] = ALIAS1.get(parts[0], parts[0])
    return "-".join(parts[:level])
