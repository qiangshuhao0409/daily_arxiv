import arxivscraper
import datetime
import time
import requests
import json
from datetime import timedelta
import os
import pathlib

# =====================================================================================
# 1. 配置区域 - 在这里添加你所有感兴趣的分类
# =====================================================================================
CATEGORIES = {
    "cs": ["cs.AI", "cs.NI", "cs.SY", "cs.IT"],
    "eess": ["eess.SP"]
}

# =====================================================================================
# 2. 核心函数
# =====================================================================================
def get_papers_with_code(date_str, cats):
    """
    抓取指定日期的论文并查找其代码库。
    @param date_str: 'YYYY-MM-DD' 格式的日期字符串
    @param cats: 分类字典
    @return: 一个字典，包含当天找到的带代码的论文
    """
    output = {}
    
    # 步骤 1: 从 arXiv 抓取论文元数据
    for cat_group, sub_cats in cats.items():
        try:
            scraper = arxivscraper.Scraper(category=cat_group, date_from=date_str, date_until=date_str, filters={'categories': sub_cats})
            papers = scraper.scrape()
            if isinstance(papers, list):
                for paper in papers:
                    if paper["id"] not in output:
                        output[paper["id"]] = paper
            time.sleep(2)  # 礼貌性等待
        except Exception as e:
            print(f"Error scraping {cat_group} for date {date_str}: {e}")

    # 步骤 2: 从 paperswithcode.com 查找代码链接
    content = {}
    base_url = "https://arxiv.paperswithcode.com/api/v0/papers/"
    
    for paper_id, paper_meta in output.items():
        paper_title = " ".join(paper_meta["title"].split())
        paper_url = paper_meta["url"]
        
        url = base_url + paper_id
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # 检查请求是否成功
            r_json = response.json()
            if r_json.get("official") and r_json["official"].get("url"):
                repo_url = r_json["official"]["url"]
                repo_name = repo_url.split("/")[-1]
                content[paper_id] = f"[{paper_title}]({paper_url})|[{repo_name}]({repo_url})|\n"
        except requests.exceptions.RequestException:
            # 大多数论文没有代码是正常的，所以静默处理
            pass
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON for paper ID: {paper_id}")
            
    return {date_str: content}

def update_json_file(filename, new_data):
    """
    读取现有的 JSON 文件，合并新数据，然后写回。
    """
    try:
        with open(filename, "r", encoding='utf-8') as f:
            content = f.read()
            if not content:
                existing_data = {}
            else:
                existing_data = json.loads(content)
    except FileNotFoundError:
        existing_data = {}

    existing_data.update(new_data)
    
    with open(filename, "w", encoding='utf-8') as f:
        json.dump(existing_data, f, indent=4)

def json_to_md(filename, days_in_readme=30):
    """
    从 JSON 文件生成 README.md。
    @param filename: JSON 文件路径
    @param days_in_readme: 在 README 主页上显示最近多少天的数据
    """
    try:
        with open(filename, "r", encoding='utf-8') as f:
            data = json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Warning: {filename} not found or is empty. Cannot generate markdown.")
        return

    # 按日期降序排序
    sorted_days = sorted(data.keys(), reverse=True)
    
    with open("README.md", "w", encoding='utf-8') as f:
        f.write("# Daily ArXiv Papers with Code\n\n")
        f.write(f"A curated list of arXiv papers with open-source implementations, focusing on the following categories: **{', '.join([item for sublist in CATEGORIES.values() for item in sublist])}**. Updated daily.\n\n")
        
        f.write(f"## Latest Updates (Last {days_in_readme} Days)\n")
        f.write("| Date | Paper Title | Code Repository |\n")
        f.write("|---|---|---|\n")

        found_papers_count = 0
        for day in sorted_days[:days_in_readme]:
            if data[day]:
                for paper_id, content_str in data[day].items():
                    f.write(f"| {day} | {content_str}")
                    found_papers_count += 1
        
        if found_papers_count == 0:
            f.write(f"| | No new papers with code found in the last {days_in_readme} days. | |\n")

    print("Finished generating README.md")

# =====================================================================================
# 3. 主程序逻辑
# =====================================================================================
if __name__ == "__main__":
    
    run_mode = os.getenv("RUN_MODE", "daily_run")  # 默认为日常运行
    json_filename = "daily.json"

    if run_mode == "first_run":
        print("--- Running in 'first_run' mode: fetching data for the last 365 days. ---")
        today = datetime.date.today()
        all_data = {}
        for i in range(365): # 爬取过去一年的数据
            day_to_fetch = str(today - timedelta(days=i))
            print(f"Fetching papers for {day_to_fetch}...")
            daily_data = get_papers_with_code(day_to_fetch, CATEGORIES)
            all_data.update(daily_data)
        
        # 首次运行时，直接覆盖写入
        with open(json_filename, "w", encoding='utf-8') as f:
            json.dump(all_data, f, indent=4)
        print(f"Successfully created {json_filename} with historical data.")

    elif run_mode == "daily_run":
        print("--- Running in 'daily_run' mode: fetching data for yesterday. ---")
        yesterday = str(datetime.date.today() - timedelta(days=1))
        
        print(f"Fetching papers for {yesterday}...")
        new_data = get_papers_with_code(yesterday, CATEGORIES)
        
        # 更新 JSON 文件
        update_json_file(json_filename, new_data)
        print(f"Successfully updated {json_filename} with data from {yesterday}.")

    else:
        print(f"Error: Unknown RUN_MODE '{run_mode}'. Exiting.")
        exit(1)
        
    # 无论哪种模式，都重新生成 Markdown
    json_to_md(json_filename, days_in_readme=30)
