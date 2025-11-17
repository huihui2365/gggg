import requests
from bs4 import BeautifulSoup
import re
import json
from pathlib import Path
from time import sleep

# ====== 配置 ======
base_url = "https://sex8zy.com"
type_id = 62  # 分类 ID
start_page = 1  # 起始页
end_page = 86  # 结束页（包含）
output_dir = Path("test/output")  # 输出目录（在 test 文件夹内）
list_path = output_dir / "result.json"
detail_path = output_dir / "detail_result.json"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# ====== 创建目录 ======
output_dir.mkdir(parents=True, exist_ok=True)

# ====== 工具函数 ======
def sanitize_filename(filename):
    """删除文件名中的非法字符，并限制文件名长度"""
    # 删除非法字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 限制文件名最大长度
    MAX_PATH_LENGTH = 200  # 可以根据需要调整长度限制
    if len(filename) > MAX_PATH_LENGTH:
        filename = filename[:MAX_PATH_LENGTH]  # 截取文件夹名称的前 200 个字符
    return filename

# ====== 第一步：抓取或加载列表页 ======
if list_path.exists():
    print(f"🍀 本地存在 {list_path}，直接读取...")
    video_list = json.load(open(list_path, "r", encoding="utf-8"))
else:
    print(f"🔎 本地未找到 {list_path}，开始抓取列表页...\n")
    video_list = []
    for page in range(start_page, end_page + 1):
        page_url = f"{base_url}/index.php/vod/type/id/{type_id}/page/{page}.html"
        print(f"  📄 正在抓取列表页（{page}/{end_page}）：{page_url}")

        try:
            response = requests.get(page_url, headers=headers, timeout=10)
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, "html.parser")

            items = soup.find_all("a", class_="row", href=True)
            print(f"     当前页找到 {len(items)} 条记录")
            for i, a_tag in enumerate(items):
                href = a_tag["href"]
                if re.match(r"/index.php/vod/detail/id/\d+\.html", href):
                    li_tag = a_tag.find("li", style=re.compile("text-align: ?left"))
                    if li_tag:
                        title = li_tag.get_text(strip=True)
                        full_url = base_url + href
                        video_list.append({"title": title, "url": full_url})
            sleep(1)
        except Exception as e:
            print(f"❌ 列表页抓取失败：{page_url}，错误：{e}")

    # 保存结果
    with open(list_path, "w", encoding="utf-8") as f:
        json.dump(video_list, f, ensure_ascii=False, indent=2)

    print(f"\n📋 列表抓取完成！共 {len(video_list)} 条，已保存到 {list_path}\n")

# ====== 第二步：抓取详情页 ======
print("🎬 开始抓取详情页内容...\n")
all_details = []
total_items = len(video_list)

for idx, item in enumerate(video_list, start=1):
    url = item["url"]
    print(f"  🔍 抓取详情（{idx}/{total_items}）：{url}")

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")

        # 封面图片
        img_tag = soup.find("img", id="detail-img")
        image_url = img_tag["src"] if img_tag else None

        # 标题（覆盖主标题）
        title_tag = soup.find("h1", class_="limit")
        title = title_tag.get_text(strip=True) if title_tag else item["title"]

        # m3u8 地址
        input_tag = soup.find("input", {"id": "playId1"})
        m3u8_full = input_tag["value"] if input_tag else ""
        m3u8_url = m3u8_full.split("$")[-1] if "$" in m3u8_full else m3u8_full

        all_details.append({
            "title": title,
            "url": url,
            "image": image_url,
            "m3u8": m3u8_url
        })

        sleep(1)

    except Exception as e:
        print(f"❌ 抓取失败：{url}，错误：{e}")

# 保存详情结果
with open(detail_path, "w", encoding="utf-8") as f:
    json.dump(all_details, f, ensure_ascii=False, indent=2)

print(f"\n✨ 完成！共抓取 {len(all_details)} 条详情内容，已保存到 {detail_path}")
