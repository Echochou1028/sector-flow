"""探测：个股资料页"所属行业"的原始链接（只打印）：python run.py probe_class"""
import re
import time

import requests

import fetch_sina

URL = "https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpOtherInfo/stockid/{}/menu_num/2.phtml"


def run():
    for code in ("688825", "600938", "688072", "300750", "600519", "000001", "601899", "002594"):
        t = requests.get(URL.format(code), headers=fetch_sina.UA, timeout=20)
        t.encoding = "gb2312"
        html = t.text
        i = html.find("所属行业板块")
        j = html.find("所属概念板块")
        seg = html[i: j if j > i else i + 1500]
        seg = re.sub(r"\s+", " ", seg)
        print(f"\n===== {code} 行业区块原始HTML（{len(seg)}字符）:\n{seg[:1500]}")
        time.sleep(0.5)
