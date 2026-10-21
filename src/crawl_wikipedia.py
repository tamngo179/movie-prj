"""
Module: crawl_wikipedia.py
Description: Thu thập nội dung, wikitext infobox và lead extract từ Wikipedia cho danh sách phim.
Author: Data Engineering Team
"""

import os
import re
import csv
import json
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path
import requests
import mwparserfromhell
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("CrawlWikipedia")

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "MovieWikiResearch/1.0 (academic research; contact@example.edu)"
HEADERS = {"User-Agent": USER_AGENT}

KNOWN_GENRES = [
    "action", "adventure", "animation", "biography", "comedy", "crime",
    "documentary", "drama", "family", "fantasy", "film noir", "history",
    "horror", "music", "musical", "mystery", "romance", "romantic comedy",
    "science fiction", "sci-fi", "short", "sport", "superhero", "thriller",
    "war", "western", "psychological thriller", "slasher", "satire", "dark comedy"
]


def clean_infobox_value(param_node) -> list:
    """
    Trích xuất và làm sạch giá trị wikitext từ tham số infobox thành danh sách chuỗi văn bản.
    Xử lý các template danh sách (ubl, plainlist, flatlist, ...), wikilinks [[Target|Label]], thẻ <ref>, <br>, v.v.
    """
    if param_node is None:
        return []

    val_str = str(param_node.value)
    # Thay thế thẻ ngắt dòng HTML <br> thành dấu xuống dòng
    val_str = re.sub(r'<br\s*/?>', '\n', val_str, flags=re.IGNORECASE)
    # Loại bỏ chú thích HTML
    val_str = re.sub(r'<!--.*?-->', '', val_str, flags=re.DOTALL)
    # Loại bỏ thẻ tham chiếu <ref>
    val_str = re.sub(r'<ref[^>]*>.*?</ref>', '', val_str, flags=re.DOTALL | re.IGNORECASE)
    val_str = re.sub(r'<ref[^>]*/>', '', val_str, flags=re.IGNORECASE)

    try:
        code = mwparserfromhell.parse(val_str)
    except Exception:
        code = val_str

    items = []
    list_templates = {"unbulleted list", "ubl", "plainlist", "flatlist", "hlist", "flat list", "flat_list"}
    has_list_tpl = False

    if hasattr(code, "filter_templates"):
        for t in code.filter_templates():
            tname = str(t.name).strip().lower()
            if tname in list_templates:
                has_list_tpl = True
                for p in t.params:
                    p_text = str(p.value.strip_code()).strip()
                    if p_text:
                        for line in p_text.splitlines():
                            line = line.strip().lstrip('*-#• ')
                            if line:
                                items.append(line)

    if not has_list_tpl and hasattr(code, "filter_wikilinks"):
        wikilinks = code.filter_wikilinks()
        if wikilinks and len(wikilinks) > 0 and len(str(code).splitlines()) <= 20:
            for wl in wikilinks:
                text = str(wl.text) if wl.text else str(wl.title)
                text = text.strip()
                if text and not text.lower().startswith(('file:', 'image:', 'category:')):
                    items.append(text)
        else:
            plain = str(code.strip_code()).strip() if hasattr(code, "strip_code") else str(code).strip()
            raw_items = re.split(r'[\n;•]+|(?<!\d),(?!\d)', plain)
            for it in raw_items:
                it = it.strip().lstrip('*-#• ')
                if it:
                    items.append(it)
    elif not has_list_tpl:
        plain = str(code).strip()
        raw_items = re.split(r'[\n;•]+|(?<!\d),(?!\d)', plain)
        for it in raw_items:
            it = it.strip().lstrip('*-#• ')
            if it:
                items.append(it)

    cleaned = []
    seen = set()
    for item in items:
        # Xóa ghi chú trong ngoặc đơn như (director), (producer)
        item = re.sub(r'\s*\([^)]*\)', '', item).strip()
        item = item.replace('\xa0', ' ').strip()
        if item and len(item) > 1 and item.lower() not in seen:
            seen.add(item.lower())
            cleaned.append(item)

    return cleaned


def parse_release_date(param_node) -> tuple:
    """
    Phân tích ngày và năm phát hành từ infobox released param.
    Trả về (release_date_str, release_year_int).
    """
    if param_node is None:
        return None, None

    val_str = str(param_node.value)
    
    # 1. Tìm template {{Film date|YYYY|MM|DD...}}
    m_film_date = re.search(r'\{\{film date\|(\d{4})\|(\d{1,2})\|(\d{1,2})', val_str, re.IGNORECASE)
    if m_film_date:
        y, m, d = m_film_date.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}", int(y)
        
    m_year_only = re.search(r'\{\{film date\|(\d{4})', val_str, re.IGNORECASE)
    if m_year_only:
        y = m_year_only.group(1)
        return y, int(y)

    # 2. Tìm định dạng YYYY-MM-DD
    m_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', val_str)
    if m_iso:
        return m_iso.group(0), int(m_iso.group(1))

    # 3. Tìm dạng Month DD, YYYY hoặc DD Month YYYY
    months = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    m_text_date = re.search(rf'({months}\s+\d{{1,2}},\s+(\d{{4}}))', val_str, re.IGNORECASE)
    if m_text_date:
        full_date, y = m_text_date.group(1), m_text_date.group(2)
        return full_date, int(y)

    m_text_date2 = re.search(rf'(\d{{1,2}}\s+{months}\s+(\d{{4}}))', val_str, re.IGNORECASE)
    if m_text_date2:
        full_date, y = m_text_date2.group(1), m_text_date2.group(2)
        return full_date, int(y)

    # 4. Tìm năm đơn thuần 2015-2025
    m_year = re.search(r'\b(20[12]\d)\b', val_str)
    if m_year:
        y = int(m_year.group(1))
        return str(y), y

    return None, None


def parse_runtime(param_node) -> str:
    """
    Trích xuất thời lượng phút từ infobox runtime.
    """
    if param_node is None:
        return None
    val_str = str(param_node.value)
    m = re.search(r'(\d{2,3})\s*(?:min|minute)', val_str, re.IGNORECASE)
    if m:
        return f"{m.group(1)} minutes"
    m_digits = re.search(r'\b(\d{2,3})\b', val_str)
    if m_digits:
        return f"{m_digits.group(1)} minutes"
    return None


def extract_genres_from_categories_and_text(categories: list, extract_text: str) -> list:
    """
    Trích xuất thể loại từ danh mục trang và câu mở đầu của Wikipedia bằng regex chuẩn.
    Tránh các trường hợp đồng âm địa lý (ví dụ: Western Australia không phải thể loại Western).
    """
    genres = set()
    film_categories = [c.lower() for c in categories if "film" in c.lower()]

    for cat_lower in film_categories:
        # Bỏ qua các danh mục về địa điểm
        if "western australia" in cat_lower or "western cape" in cat_lower or "western europe" in cat_lower:
            cat_check = re.sub(r'western\s+(?:australia|cape|europe|province)', '', cat_lower)
        else:
            cat_check = cat_lower

        for g in KNOWN_GENRES:
            if g == "western":
                pattern = r'\bwestern\s+films?\b'
            elif g == "short":
                pattern = r'\bshort\s+films?\b'
            elif g == "history":
                pattern = r'\b(?:historical|history)\s+films?\b'
            elif g == "war":
                pattern = r'\bwar\s+films?\b'
            elif g == "sport":
                pattern = r'\b(?:sports?)\s+films?\b'
            else:
                pattern = rf'\b{re.escape(g)}\b'

            if re.search(pattern, cat_check):
                g_clean = "Science Fiction" if g in ["sci-fi", "science fiction"] else g.title()
                genres.add(g_clean)

    # Trích xuất từ văn bản dẫn nhập nếu thể loại còn ít
    if len(genres) < 2 and extract_text:
        text_lower = extract_text[:350].lower()
        for g in KNOWN_GENRES:
            pattern = rf'\b{re.escape(g)}\s+(?:film|movie)'
            if re.search(pattern, text_lower):
                g_clean = "Science Fiction" if g in ["sci-fi", "science fiction"] else g.title()
                genres.add(g_clean)

    return sorted(list(genres))


def parse_movie_page(page_data: dict, target_year: int) -> dict:
    """
    Phân tích toàn bộ thông tin một bài viết phim từ Wikipedia API response.
    """
    title = page_data.get("title", "")
    pageid = page_data.get("pageid", 0)
    qid = page_data.get("pageprops", {}).get("wikibase_item")
    movie_id = qid if qid else f"WIKI_{pageid}"
    wiki_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
    extract_content = page_data.get("extract", "")

    # Lấy wikitext
    revisions = page_data.get("revisions", [])
    wikitext = revisions[0].get("slots", {}).get("main", {}).get("*", "") if revisions else ""

    parsed = mwparserfromhell.parse(wikitext)
    infoboxes = [t for t in parsed.filter_templates() if "infobox" in str(t.name).lower() and "film" in str(t.name).lower()]
    
    ib = infoboxes[0] if infoboxes else None

    # Khởi tạo các trường
    directors = []
    cast = []
    writers = []
    producers = []
    prod_companies = []
    country = []
    language = []
    release_date = None
    release_year = None
    runtime = None

    if ib:
        # Directors
        for p in ["director", "directors"]:
            if ib.has(p):
                directors.extend(clean_infobox_value(ib.get(p)))

        # Cast
        for p in ["starring", "cast"]:
            if ib.has(p):
                cast.extend(clean_infobox_value(ib.get(p)))

        # Writers
        for p in ["screenplay", "writer", "writers", "story"]:
            if ib.has(p):
                writers.extend(clean_infobox_value(ib.get(p)))

        # Producers
        for p in ["producer", "producers"]:
            if ib.has(p):
                producers.extend(clean_infobox_value(ib.get(p)))

        # Production Company & Distributor
        for p in ["studio", "production companies", "production company", "distributor"]:
            if ib.has(p):
                prod_companies.extend(clean_infobox_value(ib.get(p)))

        # Country
        for p in ["country", "countries"]:
            if ib.has(p):
                country.extend(clean_infobox_value(ib.get(p)))

        # Language
        for p in ["language", "languages"]:
            if ib.has(p):
                language.extend(clean_infobox_value(ib.get(p)))

        # Runtime
        if ib.has("runtime"):
            runtime = parse_runtime(ib.get("runtime"))

        # Release date & year
        for p in ["released", "release date", "release_date"]:
            if ib.has(p):
                rdate, ryear = parse_release_date(ib.get(p))
                if rdate and not release_date:
                    release_date = rdate
                if ryear and not release_year:
                    release_year = ryear

    if not release_year:
        release_year = target_year
    if not release_date:
        release_date = str(release_year)

    # Lấy categories từ cả wikitext và page_data
    wikitext_cats = [str(wl.title) for wl in parsed.filter_wikilinks() if str(wl.title).startswith("Category:")]
    api_cats = [c.get("title", "") for c in page_data.get("categories", [])]
    all_categories = list(set(wikitext_cats + api_cats))
    genres = extract_genres_from_categories_and_text(all_categories, extract_content)

    return {
        "movie_id": movie_id,
        "title": title,
        "release_year": int(release_year),
        "release_date": release_date,
        "director": directors,
        "cast": cast,
        "writer": writers,
        "producer": producers,
        "production_company": prod_companies,
        "genre": genres,
        "country": country,
        "language": language,
        "runtime": runtime,
        "wiki_url": wiki_url,
        "content": extract_content.strip()
    }


def crawl_candidates(candidate_file: Path, output_file: Path, log_file: Path, batch_size: int = 15, max_limit: int = None):
    """
    Crawl danh sách phim theo batch từ Wikipedia API với checkpointing và logging.
    """
    with open(candidate_file, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    if max_limit:
        candidates = candidates[:max_limit]

    logger.info(f"Đọc {len(candidates)} ứng viên từ {candidate_file}")

    # Đọc checkpoint nếu đã có
    crawled_ids = set()
    crawled_titles = set()
    if output_file.exists():
        with open(output_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        obj = json.loads(line)
                        crawled_ids.add(obj.get("movie_id"))
                        crawled_titles.add(obj.get("title"))
                    except Exception:
                        pass
        logger.info(f"Đã có {len(crawled_titles)} phim trong checkpoint {output_file.name}")

    # Chuẩn bị file log
    log_exists = log_file.exists()
    log_fp = open(log_file, "a", newline="", encoding="utf-8")
    log_writer = csv.DictWriter(
        log_fp,
        fieldnames=["movie_id", "title", "target_year", "status", "error_reason", "timestamp"]
    )
    if not log_exists:
        log_writer.writeheader()

    out_fp = open(output_file, "a", encoding="utf-8")

    # Lọc các ứng viên chưa crawl
    remaining = [c for c in candidates if c.get("title") not in crawled_titles and c.get("movie_id") not in crawled_ids]
    logger.info(f"Cần crawl tiếp: {len(remaining)} phim...")

    url = "https://en.wikipedia.org/w/api.php"

    for i in tqdm(range(0, len(remaining), batch_size), desc="Crawling Wikipedia"):
        batch = remaining[i : i + batch_size]
        title_map = {m["title"]: m for m in batch}
        titles_str = "|".join(title_map.keys())

        params = {
            "action": "query",
            "prop": "revisions|extracts|pageprops|categories",
            "rvprop": "content",
            "rvslots": "main",
            "exintro": True,
            "explaintext": True,
            "cllimit": 50,
            "titles": titles_str,
            "format": "json"
        }

        success = False
        retries = 3
        data = None

        for attempt in range(retries):
            try:
                res = requests.get(url, params=params, headers=HEADERS, timeout=35)
                if res.status_code == 200:
                    data = res.json()
                    success = True
                    break
                elif res.status_code == 429:
                    logger.warning(f"Rate limited (429). Ngủ 5 giây trước khi thử lại...")
                    time.sleep(5)
                else:
                    time.sleep(1 * (attempt + 1))
            except Exception as e:
                time.sleep(1.5 * (attempt + 1))

        now_str = datetime.now().isoformat()

        if not success or not data:
            # Ghi log thất bại cả batch
            for m in batch:
                log_writer.writerow({
                    "movie_id": m.get("movie_id", ""),
                    "title": m.get("title", ""),
                    "target_year": m.get("target_year", ""),
                    "status": "FAILED",
                    "error_reason": "API request failed after retries",
                    "timestamp": now_str
                })
            log_fp.flush()
            continue

        pages = data.get("query", {}).get("pages", {})
        for pid, pdata in pages.items():
            title = pdata.get("title")
            target_meta = title_map.get(title, {})
            target_year = target_meta.get("target_year", 2020)

            if "missing" in pdata:
                log_writer.writerow({
                    "movie_id": target_meta.get("movie_id", ""),
                    "title": title,
                    "target_year": target_year,
                    "status": "FAILED",
                    "error_reason": "Page missing on Wikipedia",
                    "timestamp": now_str
                })
                continue

            try:
                parsed_movie = parse_movie_page(pdata, target_year)
                out_fp.write(json.dumps(parsed_movie, ensure_ascii=False) + "\n")
                out_fp.flush()

                log_writer.writerow({
                    "movie_id": parsed_movie.get("movie_id", ""),
                    "title": parsed_movie.get("title", ""),
                    "target_year": target_year,
                    "status": "SUCCESS",
                    "error_reason": "",
                    "timestamp": now_str
                })
            except Exception as err:
                log_writer.writerow({
                    "movie_id": target_meta.get("movie_id", ""),
                    "title": title,
                    "target_year": target_year,
                    "status": "FAILED",
                    "error_reason": f"Parse error: {str(err)}",
                    "timestamp": now_str
                })

        log_fp.flush()
        time.sleep(0.1)  # Giới hạn tốc độ

    out_fp.close()
    log_fp.close()
    logger.info("Quá trình crawl hoàn tất.")


def main():
    parser = argparse.ArgumentParser(description="Crawl dữ liệu phim từ Wikipedia")
    parser.add_argument("--candidates", type=str, default=None, help="Đường dẫn file candidates json")
    parser.add_argument("--output", type=str, default=None, help="Đường dẫn file output jsonl")
    parser.add_argument("--log", type=str, default=None, help="Đường dẫn file crawl log csv")
    parser.add_argument("--batch_size", type=int, default=15, help="Kích thước batch mỗi request")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số phim crawl để test")
    args = parser.parse_args()

    candidates_path = Path(args.candidates) if args.candidates else RAW_DIR / "movie_candidates.json"
    output_path = Path(args.output) if args.output else RAW_DIR / "raw_movies.jsonl"
    log_path = Path(args.log) if args.log else RAW_DIR / "crawl_log.csv"

    if not candidates_path.exists():
        logger.error(f"Không tìm thấy file ứng viên: {candidates_path}. Vui lòng chạy collect_movies.py trước!")
        return

    crawl_candidates(
        candidate_file=candidates_path,
        output_file=output_path,
        log_file=log_path,
        batch_size=args.batch_size,
        max_limit=args.limit
    )


if __name__ == "__main__":
    main()
