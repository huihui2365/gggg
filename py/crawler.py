# crawler.py  —— 专为 GitHub Actions 优化版（type_id=63）
import json
import random
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

# ==================== 配置 ====================
base_url = "https://sex8zy.com"
type_id = 63
start_page = 1
end_page = 2                     # 你现在只跑2页，后面想跑更多直接改数字
output_dir = Path("test/output")
list_path = output_dir / "result.json"
detail_path = output_dir / "detail_result.json"

MAX_WORKERS = 15                 # GitHub Actions 最佳值（别超过20）
TIMEOUT = 20

# 随机UA池
UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
]

# 创建带重试的 Session
session = requests.Session()
retry = Retry(total=3, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(pool_connections=50, pool_maxsize=MAX_WORKERS*2, max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

output_dir.mkdir(parents=True, exist_ok=True)

# ==================== 第一步：并发抓列表 ====================
if list_path.exists():
    print("检测到已有 result.json，直接加载...")
    video_list = json.load(open(list_path, "r", encoding="utf-8"))
else:
    print(f"开始并发抓取第 {start_page}-{end_page} 页列表...")
    video_list = []

    def fetch_list_page(page):
        url = f"{base_url}/index.php/vod/type/id/{type_id}/page/{page}.html"
        headers = {"User-Agent": random.choice(UA_LIST)}
        try:
            r = session.get(url, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, "html.parser")
            items = []
            for a in soup.find_all("a", class_="row", href=True):
                href = a["href"]
                if re.match(r"/index.php/vod/detail/id/\d+\.html", href):
                    li = a.find("li", style=re.compile("text-align: ?left"))
                    if li:
                        title = li.get_text(strip=True)
                        items.append({"title": title, "url": base_url + href})
            print(f"第 {page} 页 → {len(items)} 条")
            return items
        except Exception as e:
            print(f"第 {page} 页失败：{e}")
            return []

    with ThreadPoolExecutor(max_workers=10) as executor:
        for items in executor.map(fetch_list_page, range(start_page, end_page + 1)):
            video_list.extend(items)
            sleep(random.uniform(0.5, 1.2))

    with open(list_path, "w", encoding="utf-8") as f:
        json.dump(video_list, f, ensure_ascii=False, indent=2)
    print(f"列表完成！共 {len(video_list)} 条\n")

# ==================== 第二步：并发抓详情 ====================
def fetch_detail(task):
    idx, total, item = task
    url = item["url"]
    headers = {"User-Agent": random.choice(UA_LIST)}
    try:
        r = session.get(url, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")

        img = soup.find("img", id="detail-img")["src"] if soup.find("img", id="detail-img") else None
        title = soup.find("h1", class_="limit").get_text(strip=True) if soup.find("h1", class_="limit") else item["title"]
        m3u8_input = soup.find("input", id="playId1")
        m3u8 = (m3u8_input["value"].split("$")[-1] if m3u8_input and "$" in m3u8_input["value"] else 
                m3u8_input["value"] if m3u8_input else "")

        return {
            "title": title,
            "url": url,
            "image": img,
            "m3u8": m3u8.strip()
        }
    except Exception as e:
        return {"title": "【失败】" + item["title"], "url": url, "image": None, "m3u8": "", "error": str(e)}

# 如果已有完整详情且数量一致就跳过
if detail_path.exists() and len(json.load(open(detail_path))) >= len(video_list):
    print("detail_result.json 已存在且完整，直接结束")
else:
    print(f"开始并发抓取 {len(video_list)} 条详情（线程数：{MAX_WORKERS}）...")
    tasks = [(i+1, len(video_list), item) for i, item in enumerate(video_list)]
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for future in as_completed({executor.submit(fetch_detail, t): t[0] for t in tasks}.keys()):
            result = future.result()
            results.append(result)
            status = "成功" if "error" not in result else "失败"
            print(f"[{result['url'].split('/')[-1]:>15}] {status} {result['title'][:40]}")

    # 保持原始顺序
    results = sorted(results, key=lambda x: video_list.index(next(i for i in video_list if i["url"] == x["url"])))

    with open(detail_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n全部完成！结果保存在：{detail_path}")
