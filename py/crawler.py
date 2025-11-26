#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import random
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from time import sleep

# ========== 配置 ==========
base_url = "http://fhzy10.com/"
type_id = 2
start_page = 1
end_page = 187
output_dir = Path("/volume1/docker/python_scripts/ddd")
list_path = output_dir / "result_list.json"
detail_path = output_dir / "result_detail.json"

MAX_WORKERS = 12
TIMEOUT = 15
RETRY_COUNT = 3
UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

output_dir.mkdir(parents=True, exist_ok=True)

# ========== requests Session ==========
session = requests.Session()
retry = Retry(total=RETRY_COUNT, backoff_factor=1.5,
              status_forcelist=[429, 500, 502, 503, 504],
              allowed_methods=frozenset(["GET"]))
adapter = HTTPAdapter(pool_connections=50, pool_maxsize=MAX_WORKERS * 2, max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

def pick_header():
    return {"User-Agent": random.choice(UA_LIST)}

# ========== 列表页抓取 ==========
video_list = []
for page in range(start_page, end_page + 1):
    url = f"{base_url.rstrip('/')}/index.php/vod/type/id/{type_id}/page/{page}.html"
    try:
        r = session.get(url, headers=pick_header(), timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")

        for li in soup.select("ul.nr > li"):
            a = li.select_one("a[href^='/index.php/vod/detail/id/']")
            if a:
                href = a.get("href").strip()
                title = a.get_text(strip=True)
                full_url = urljoin(base_url, href)
                video_list.append({"title": title, "url": full_url})
        sleep(random.uniform(0.2, 0.5))
        print(f"第 {page} 页抓取完成，共 {len(video_list)} 条")
    except Exception as e:
        print(f"第 {page} 页抓取失败: {e}")

# 去重
seen = set()
uniq_list = []
for item in video_list:
    if item["url"] not in seen:
        seen.add(item["url"])
        uniq_list.append(item)
video_list = uniq_list
print(f"去重后列表数量: {len(video_list)} 条")

with open(list_path, "w", encoding="utf-8") as f:
    json.dump(video_list, f, ensure_ascii=False, indent=2)

# ========== 详情页抓取 ==========
def fetch_detail(idx, url):
    try:
        r = session.get(url, headers=pick_header(), timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")

        # 图片
        img_tag = soup.select_one("div.vodImg img")
        image = None
        if img_tag:
            for attr in ("data-original", "data-src", "src"):
                if img_tag.get(attr):
                    image = urljoin(url, img_tag.get(attr))
                    break

        # 标题
        h1_tag = soup.select_one("h1.limit")
        vodh_tag = soup.select_one("div.vodh")
        if h1_tag and h1_tag.get_text(strip=True):
            title = h1_tag.get_text(strip=True)
        elif vodh_tag and vodh_tag.get_text(strip=True):
            title = vodh_tag.get_text(strip=True)
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()
        else:
            title = f"未知标题-{idx}"

        # 取第一条 m3u8
        m3u8 = ""
        found = False
        for vp in soup.select("div.vodplayinfo"):
            if found:
                break
            # input
            inp = vp.select_one("input[value*='.m3u8']")
            if inp and inp.get("value"):
                v = inp["value"].strip()
                m3u8 = v.split("$")[-1] if "$" in v else v
                found = True
                break
            # a 标签
            a_tag = vp.select_one("a[href*='.m3u8']")
            if a_tag:
                m3u8 = a_tag.get("href").strip()
                found = True
                break
            # 文本
            a_tag2 = vp.select_one("a")
            if a_tag2 and "$" in a_tag2.get_text(strip=True):
                m3u8 = a_tag2.get_text(strip=True).split("$")[-1]
                found = True
                break

        return {"title": title, "url": url, "image": image, "m3u8": m3u8}

    except Exception as e:
        return {"title": "抓取失败", "url": url, "image": None, "m3u8": "", "error": str(e)}

results = []
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    futures = {ex.submit(fetch_detail, i+1, item["url"]): item for i, item in enumerate(video_list)}
    for fut in as_completed(futures):
        res = fut.result()
        results.append(res)
        print(f"[{len(results)}/{len(video_list)}] {res['title'][:30]}")

with open(detail_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n抓取完成！共 {len(results)} 条 → {detail_path}")

