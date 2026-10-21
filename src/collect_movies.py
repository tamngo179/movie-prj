"""
Module: collect_movies.py
Description: Thu thập danh sách các phim điện ảnh (2015-2025) từ Wikipedia API & Wikidata
Author: Data Engineering Team
"""

import os
import json
import time
import logging
import argparse
import requests
from pathlib import Path
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("CollectMovies")

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATES_FILE = RAW_DIR / "movie_candidates.json"

USER_AGENT = "MovieWikiResearch/1.0 (academic research; contact@example.edu)"
HEADERS = {"User-Agent": USER_AGENT}

YEARS = list(range(2015, 2026))  # 2015 to 2025


def fetch_category_movies_for_year(year: int, max_per_year: int = 600) -> list:
    """
    Thu thập danh sách tiêu đề bài viết phim từ Wikipedia Category:{year}_films.
    Sử dụng pagination (cmcontinue) để lấy đủ số lượng.
    """
    category_title = f"Category:{year}_films"
    url = "https://en.wikipedia.org/w/api.php"
    movies = []
    cmcontinue = None
    
    logger.info(f"Đang thu thập phim năm {year} từ {category_title}...")
    
    while len(movies) < max_per_year:
        limit = min(500, max_per_year - len(movies))
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category_title,
            "cmlimit": limit,
            "cmtype": "page",
            "format": "json"
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
            
        try:
            res = requests.get(url, params=params, headers=HEADERS, timeout=30)
            res.raise_for_rate_limit = True
            if res.status_code != 200:
                logger.warning(f"Lỗi HTTP {res.status_code} khi query {category_title}")
                break
                
            data = res.json()
            members = data.get("query", {}).get("categorymembers", [])
            if not members:
                break
                
            for m in members:
                title = m.get("title", "")
                pageid = m.get("pageid")
                # Bỏ qua các trang danh sách tổng hợp, thể loại, hoặc định hướng
                if title.startswith(("List of", "Lists of", "Index of", "Category:", "Template:")):
                    continue
                movies.append({
                    "title": title,
                    "pageid": pageid,
                    "target_year": year
                })
                if len(movies) >= max_per_year:
                    break
                    
            cmcontinue = data.get("continue", {}).get("cmcontinue")
            if not cmcontinue:
                break
                
            time.sleep(0.1)  # Giới hạn tốc độ lịch sự
        except Exception as e:
            logger.error(f"Ngoại lệ khi gọi Wikipedia API cho năm {year}: {e}")
            break
            
    logger.info(f"Năm {year}: Đã thu thập {len(movies)} phim ứng viên.")
    return movies


def enrich_with_wikidata_ids(movie_list: list, batch_size: int = 50) -> list:
    """
    Bổ sung Wikidata QID (wikibase_item) cho danh sách phim bằng pageprops API.
    """
    url = "https://en.wikipedia.org/w/api.php"
    enriched = []
    
    logger.info(f"Đang bổ sung Wikidata ID cho {len(movie_list)} phim (batch size={batch_size})...")
    
    for i in range(0, len(movie_list), batch_size):
        batch = movie_list[i : i + batch_size]
        title_map = {m["title"]: m for m in batch}
        titles_str = "|".join(title_map.keys())
        
        params = {
            "action": "query",
            "prop": "pageprops",
            "ppprop": "wikibase_item",
            "titles": titles_str,
            "format": "json"
        }
        
        try:
            res = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if res.status_code == 200:
                data = res.json()
                pages = data.get("query", {}).get("pages", {})
                for pid, pdata in pages.items():
                    title = pdata.get("title")
                    qid = pdata.get("pageprops", {}).get("wikibase_item")
                    if title in title_map:
                        item = title_map[title].copy()
                        item["movie_id"] = qid if qid else f"WIKI_{item['pageid']}"
                        item["wiki_url"] = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                        enriched.append(item)
            else:
                for item in batch:
                    item["movie_id"] = f"WIKI_{item['pageid']}"
                    item["wiki_url"] = f"https://en.wikipedia.org/wiki/{item['title'].replace(' ', '_')}"
                    enriched.append(item)
            time.sleep(0.05)
        except Exception as e:
            logger.error(f"Lỗi khi lấy pageprops cho batch: {e}")
            for item in batch:
                item["movie_id"] = f"WIKI_{item['pageid']}"
                item["wiki_url"] = f"https://en.wikipedia.org/wiki/{item['title'].replace(' ', '_')}"
                enriched.append(item)
                
    return enriched


def main():
    parser = argparse.ArgumentParser(description="Thu thập danh sách phim 2015-2025 từ Wikipedia/Wikidata")
    parser.add_argument("--target", type=int, default=5200, help="Tổng số phim mục tiêu cần thu thập ứng viên (mặc định 5200 để trừ hao)")
    parser.add_argument("--test", type=int, default=None, help="Chế độ test nhanh với số lượng nhỏ (ví dụ 100)")
    args = parser.parse_args()

    total_target = args.test if args.test else args.target
    years_count = len(YEARS)
    per_year = max(10, total_target // years_count + (10 if total_target % years_count else 0))
    
    logger.info(f"=== Bắt đầu thu thập danh sách phim ===")
    logger.info(f"Mục tiêu: {total_target} phim (khoảng {per_year} phim/năm từ 2015 đến 2025)")
    
    all_raw_movies = []
    seen_titles = set()
    
    for year in YEARS:
        year_movies = fetch_category_movies_for_year(year, max_per_year=per_year)
        for m in year_movies:
            if m["title"] not in seen_titles:
                seen_titles.add(m["title"])
                all_raw_movies.append(m)
        if len(all_raw_movies) >= total_target:
            break
            
    all_raw_movies = all_raw_movies[:total_target]
    logger.info(f"Tổng số phim thu thập trước khi lấy Wikidata ID: {len(all_raw_movies)}")
    
    # Bổ sung Wikidata ID
    enriched_movies = enrich_with_wikidata_ids(all_raw_movies)
    
    # Lưu vào checkpoint
    output_file = CANDIDATES_FILE if not args.test else RAW_DIR / f"movie_candidates_test_{args.test}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(enriched_movies, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Đã lưu {len(enriched_movies)} phim ứng viên vào: {output_file}")


if __name__ == "__main__":
    main()
