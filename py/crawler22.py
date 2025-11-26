# crawler.py
import json
import random
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
from urllib3.util import Retry
from requests.adapters import HTTPAdapter
from time import sleep

# ==================== 配置 ====================
base_url = "https://sex8zy.com"
type_id = 55
start_page = 1
end_page = 121
output_dir = Path("test/output")
list_path = output_dir / "result4.json"
detail_path = output_dir / "detail_result4.json"

MAX_WORKERS = 15
TIMEOUT = 20

UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
]

session = requests.Session()
retry = Retry(total=3, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(pool_connections=50, pool_maxsize=MAX_WORKERS*2, max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

output_dir.mkdir(parents=True, exist_ok=True)

# ==================== 列表页 ====================
if list_path.exists():
    print("加载已有 result.json")
    video_list = json.load(open(list_path, "r", encoding="utf-8"))
else:
    print("抓取列表页...")
    video_list = []
    def fetch_list(p):
        url = f"{base_url}/index.php/vod/type/id/{type_id}/page/{p}.html"
        try:
            r = session.get(url, headers={"User-Agent": random.choice(UA_LIST)}, timeout=TIMEOUT)
            r.raise_for_status()
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, "html.parser")
            items = []
            for a in soup.find_all("a", class_="row", href=True):
                if re.match(r"/index.php/vod/detail/id/\d+\.html", a["href"]):
                    li = a.find("li", style=re.compile("text-align"))
                    if li:
                        items.append({"title": li.text.strip(), "url": base_url + a["href"]})
            print(f"第{p}页: {len(items)}条")
            return items
        except Exception as e:
            print(f"第{p}页失败: {e}")
            return []

    with ThreadPoolExecutor(max_workers=10) as ex:
        for items in ex.map(fetch_list, range(start_page, end_page+1)):
            video_list.extend(items)
            sleep(random.uniform(0.5, 1.2))

    json.dump(video_list, open(list_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# ==================== 详情页 ====================
def fetch_detail(task):
    idx, item = task
    try:
        r = session.get(item["url"], headers={"User-Agent": random.choice(UA_LIST)}, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        s = BeautifulSoup(r.text, "html.parser")
        img = s.find("img", id="detail-img")["src"] if s.find("img", id="detail-img") else None
        title = s.find("h1", class_="limit").get_text(strip=True) if s.find("h1", class_="limit") else item["title"]
        m3u8 = ""
        inp = s.find("input", id="playId1")
        if inp and inp.get("value"):
            val = inp["value"]
            m3u8 = val.split("$")[-1] if "$" in val else val
        return {"title": title, "url": item["url"], "image": img, "m3u8": m3u8.strip()}
    except Exception as e:
        return {"title": "[失败]"+item["title"], "url": item["url"], "image": None, "m3u8": "", "error": str(e)}

if not detail_path.exists() or len(json.load(open(detail_path))) < len(video_list):
    print(f"并发抓取 {len(video_list)} 条详情...")
    tasks = [(i, item) for i, item in enumerate(video_list)]
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for future in as_completed({ex.submit(fetch_detail, t): t for t in tasks}):
            results.append(future.result())
    # 保持原顺序
    results = [r for _, item in tasks for r in results if r["url"] == item["url"]]
    json.dump(results, open(detail_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"全部完成 → {detail_path}")
