"""
Module: preprocess.py
Description: Tiền xử lý, chuẩn hóa, làm sạch và loại bỏ trùng lặp cho dữ liệu phim.
Author: Data Engineering Team
"""

import os
import re
import json
import logging
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("Preprocess")

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

RAW_MOVIES_FILE = RAW_DIR / "raw_movies.jsonl"
PROCESSED_MOVIES_FILE = PROCESSED_DIR / "movies.csv"


def clean_title(title: str) -> str:
    """
    Chuẩn hóa tên phim, loại bỏ hậu tố định hướng như (film), (2020 film),...
    """
    if not title:
        return ""
    cleaned = re.sub(r'\s*\((?:\d{4}\s+)?(?:film|movie|miniseries|series)\)', '', title, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\(film\s+series\)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\(upcoming\s+film\)', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def parse_runtime_minutes(runtime_val) -> float:
    """
    Chuẩn hóa thời lượng thành số nguyên phút (hoặc np.nan nếu không có).
    """
    if not runtime_val or pd.isna(runtime_val):
        return np.nan
    val_str = str(runtime_val)
    m = re.search(r'(\d{2,3})\s*(?:min|minute)', val_str, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m_hours = re.search(r'(\d+)\s*(?:h|hr|hour)s?\s*(\d+)?\s*(?:m|min)?', val_str, re.IGNORECASE)
    if m_hours:
        hrs = int(m_hours.group(1))
        mins = int(m_hours.group(2)) if m_hours.group(2) else 0
        return float(hrs * 60 + mins)
    m_num = re.search(r'\b(\d{2,3})\b', val_str)
    if m_num:
        val = int(m_num.group(1))
        if 20 <= val <= 600:
            return float(val)
    return np.nan


def clean_person_or_org_name(name: str) -> str:
    """
    Chuẩn hóa tên người hoặc tổ chức, loại bỏ các ký tự đặc biệt, HTML entity, hoặc ghi chú thừa.
    """
    if not name:
        return ""
    name = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', name)  # Wikilinks còn sót
    name = re.sub(r'\s*\([^)]*\)', '', name)  # Ghi chú trong ngoặc
    name = re.sub(r'\s*\[\d+\]', '', name)  # Citations [1]
    name = name.replace('&amp;', '&').replace('&#39;', "'").replace('&quot;', '"').replace('\xa0', ' ')
    name = re.sub(r'\s+', ' ', name)
    return name.strip()


def list_to_joined_str(val_list) -> str:
    """
    Chuyển danh sách thành chuỗi phân cách bởi ' ; ', loại bỏ phần tử rỗng và trùng.
    """
    if not val_list:
        return ""
    if isinstance(val_list, str):
        val_list = [val_list]
    cleaned = []
    seen = set()
    for item in val_list:
        c = clean_person_or_org_name(str(item))
        if c and len(c) > 1 and c.lower() not in seen:
            seen.add(c.lower())
            cleaned.append(c)
    return " ; ".join(cleaned)


def clean_content_text(text: str) -> str:
    """
    Làm sạch đoạn văn bản giới thiệu phim, xóa citations [1], [2], khoảng trắng thừa.
    """
    if not text:
        return ""
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\[note\s+\d+\]', '', text, flags=re.IGNORECASE)
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def preprocess_dataset(input_jsonl: Path, output_csv: Path) -> pd.DataFrame:
    """
    Tiền xử lý toàn bộ tập dữ liệu phim đã crawl.
    """
    logger.info(f"Bắt đầu tiền xử lý từ {input_jsonl}...")
    records = []
    with open(input_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    records.append(json.loads(line))
                except Exception as e:
                    logger.warning(f"Bỏ qua dòng lỗi JSON: {e}")

    total_raw = len(records)
    logger.info(f"Tổng số bản ghi thô: {total_raw}")

    # Chuyển đổi thành DataFrame
    df = pd.DataFrame(records)

    # 1. Phát hiện và loại bỏ trùng lặp
    # Chuẩn hóa URL để deduplicate
    df["norm_url"] = df["wiki_url"].astype(str).str.lower().str.rstrip("/")
    
    # Tính điểm phong phú dữ liệu để giữ lại bản ghi có nhiều thông tin nhất
    def compute_completeness(row):
        score = 0
        for col in ["director", "cast", "writer", "producer", "production_company", "genre", "country", "language", "runtime", "content"]:
            val = row.get(col)
            if val is None:
                continue
            if isinstance(val, (list, tuple, set, str)):
                if len(val) > 0 and val != "":
                    score += 1
            elif isinstance(val, (int, float)):
                if not np.isnan(val):
                    score += 1
        return score

    df["completeness_score"] = df.apply(compute_completeness, axis=1)
    df = df.sort_values(by="completeness_score", ascending=False)

    # Deduplicate theo movie_id nếu có QID hợp lệ (Qxxx)
    mask_qid = df["movie_id"].astype(str).str.startswith("Q")
    df_qid = df[mask_qid].drop_duplicates(subset=["movie_id"], keep="first")
    df_non_qid = df[~mask_qid].drop_duplicates(subset=["norm_url"], keep="first")
    
    df_dedup = pd.concat([df_qid, df_non_qid]).drop_duplicates(subset=["norm_url"], keep="first")
    total_dedup = len(df_dedup)
    dup_count = total_raw - total_dedup
    logger.info(f"Số bản ghi trùng lặp bị loại bỏ: {dup_count} ({dup_count/total_raw*100:.2f}%)")

    # 2. Lọc phim ngoài giai đoạn 2015-2025
    df_dedup["release_year"] = pd.to_numeric(df_dedup["release_year"], errors="coerce").fillna(0).astype(int)
    valid_year_mask = (df_dedup["release_year"] >= 2015) & (df_dedup["release_year"] <= 2025)
    df_filtered = df_dedup[valid_year_mask].copy()
    filtered_out_years = total_dedup - len(df_filtered)
    logger.info(f"Bản ghi có năm phát hành hợp lệ (2015-2025): {len(df_filtered)} (loại {filtered_out_years} bản ghi ngoài khoảng)")

    # 3. Chuẩn hóa các trường dữ liệu
    df_filtered["title_clean"] = df_filtered["title"].apply(clean_title)
    df_filtered["runtime_minutes"] = df_filtered["runtime"].apply(parse_runtime_minutes)

    df_filtered["director_clean"] = df_filtered["director"].apply(list_to_joined_str)
    df_filtered["cast_clean"] = df_filtered["cast"].apply(list_to_joined_str)
    df_filtered["writer_clean"] = df_filtered["writer"].apply(list_to_joined_str)
    df_filtered["producer_clean"] = df_filtered["producer"].apply(list_to_joined_str)
    df_filtered["production_company_clean"] = df_filtered["production_company"].apply(list_to_joined_str)
    df_filtered["genre_clean"] = df_filtered["genre"].apply(list_to_joined_str)
    df_filtered["country_clean"] = df_filtered["country"].apply(list_to_joined_str)
    df_filtered["language_clean"] = df_filtered["language"].apply(list_to_joined_str)
    df_filtered["content_clean"] = df_filtered["content"].apply(clean_content_text)

    # 4. Tạo bảng kết quả chuẩn gồm đúng 15 trường yêu cầu
    final_cols = {
        "movie_id": "movie_id",
        "title_clean": "title",
        "release_year": "release_year",
        "release_date": "release_date",
        "director_clean": "director",
        "cast_clean": "cast",
        "writer_clean": "writer",
        "producer_clean": "producer",
        "production_company_clean": "production_company",
        "genre_clean": "genre",
        "country_clean": "country",
        "language_clean": "language",
        "runtime_minutes": "runtime",
        "wiki_url": "wiki_url",
        "content_clean": "content"
    }

    df_out = df_filtered[list(final_cols.keys())].rename(columns=final_cols)
    
    # Sắp xếp theo năm phát hành và tiêu đề
    df_out = df_out.sort_values(by=["release_year", "title"], ascending=[True, True]).reset_index(drop=True)

    # Nếu số lượng vượt quá 5.000, lấy đúng 5.000 phim chất lượng cao nhất
    if len(df_out) > 5000:
        df_out = df_out.iloc[:5000].copy()

    # Lưu ra CSV
    df_out.to_csv(output_csv, index=False, encoding="utf-8-sig")
    logger.info(f"Đã lưu {len(df_out)} phim chuẩn hóa vào: {output_csv}")

    # Báo cáo tỷ lệ thiếu dữ liệu
    logger.info("=== Tỷ lệ thiếu dữ liệu theo trường ===")
    missing_stats = {}
    for col in df_out.columns:
        if col == "runtime":
            missing = df_out[col].isna().sum()
        else:
            missing = ((df_out[col] == "") | df_out[col].isna()).sum()
        rate = missing / len(df_out) * 100
        missing_stats[col] = {"missing_count": int(missing), "missing_rate_pct": round(rate, 2)}
        logger.info(f" - {col:20s}: {missing:5d} / {len(df_out)} ({rate:5.1f}%)")

    return df_out


def main():
    parser = argparse.ArgumentParser(description="Tiền xử lý và chuẩn hóa dữ liệu phim")
    parser.add_argument("--input", type=str, default=None, help="Đường dẫn file raw movies jsonl")
    parser.add_argument("--output", type=str, default=None, help="Đường dẫn file movies csv đã xử lý")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else RAW_MOVIES_FILE
    output_path = Path(args.output) if args.output else PROCESSED_MOVIES_FILE

    if not input_path.exists():
        logger.error(f"Không tìm thấy file dữ liệu thô: {input_path}")
        return

    preprocess_dataset(input_path, output_path)


if __name__ == "__main__":
    main()
