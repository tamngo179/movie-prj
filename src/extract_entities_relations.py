"""
Module: extract_entities_relations.py
Description: Trích xuất thực thể (Entities) và quan hệ (Relations) từ dữ liệu phim đã làm sạch.
Author: Data Engineering Team
"""

import os
import re
import csv
import hashlib
import logging
import argparse
from pathlib import Path
import pandas as pd
import spacy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ExtractEntitiesRelations")

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

INPUT_MOVIES_CSV = PROCESSED_DIR / "movies.csv"
ENTITIES_CSV = PROCESSED_DIR / "entities.csv"
RELATIONS_CSV = PROCESSED_DIR / "relations.csv"

# Tải spaCy mô hình tiếng Anh cho NER bổ sung
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    logger.warning("Không tìm thấy en_core_web_sm, dùng spacy.blank('en') thay thế.")
    nlp = spacy.blank("en")


def generate_entity_id(entity_type: str, name: str) -> str:
    """
    Tạo ID định danh duy nhất ổn định (deterministic) cho thực thể dựa trên loại và tên.
    """
    prefix_map = {
        "Movie": "MOV",
        "Person": "PER",
        "Genre": "GEN",
        "Organization": "ORG",
        "Country": "COU",
        "Language": "LAN"
    }
    p = prefix_map.get(entity_type, "ENT")
    h = hashlib.md5(name.strip().lower().encode("utf-8")).hexdigest()[:8]
    return f"{p}_{h}"


def extract_entities_and_relations(movies_df: pd.DataFrame, entities_file: Path, relations_file: Path):
    """
    Trích xuất toàn bộ thực thể và quan hệ từ tập dữ liệu phim.
    """
    logger.info(f"Bắt đầu trích xuất thực thể và quan hệ từ {len(movies_df)} phim...")

    # Dictionary lưu trữ thực thể: entity_id -> {"entity_id": ..., "entity_name": ..., "entity_type": ...}
    entities = {}
    # Danh sách các quan hệ: {"source_id", "relation_type", "target_id", "source_url", "evidence_text", "extraction_method"}
    relations = []
    seen_relations = set()

    def add_entity(e_type: str, name: str, custom_id: str = None) -> str:
        name_clean = name.strip()
        if not name_clean:
            return None
        eid = custom_id if custom_id else generate_entity_id(e_type, name_clean)
        if eid not in entities:
            entities[eid] = {
                "entity_id": eid,
                "entity_name": name_clean,
                "entity_type": e_type
            }
        return eid

    def add_relation(src_id: str, rel_type: str, tgt_id: str, url: str, evidence: str, method: str):
        if not src_id or not tgt_id:
            return
        key = (src_id, rel_type, tgt_id)
        if key not in seen_relations:
            seen_relations.add(key)
            relations.append({
                "source_id": src_id,
                "relation_type": rel_type,
                "target_id": tgt_id,
                "source_url": url,
                "evidence_text": evidence[:250].strip() if evidence else "",
                "extraction_method": method
            })

    for idx, row in movies_df.iterrows():
        movie_title = str(row.get("title", "")).strip()
        movie_qid = str(row.get("movie_id", "")).strip()
        wiki_url = str(row.get("wiki_url", "")).strip()
        content = str(row.get("content", "")).strip()

        # Tạo thực thể Movie
        movie_eid = movie_qid if movie_qid.startswith("Q") else generate_entity_id("Movie", movie_title)
        add_entity("Movie", movie_title, custom_id=movie_eid)

        # 1. Đạo diễn (DIRECTED_BY) từ metadata
        directors = [d.strip() for d in str(row.get("director", "")).split(" ; ") if d.strip()]
        for d in directors:
            pid = add_entity("Person", d)
            add_relation(movie_eid, "DIRECTED_BY", pid, wiki_url, f"Director: {d}", "infobox_metadata")

        # 2. Diễn viên (ACTED_BY) từ metadata
        actors = [a.strip() for a in str(row.get("cast", "")).split(" ; ") if a.strip()]
        for a in actors:
            pid = add_entity("Person", a)
            add_relation(movie_eid, "ACTED_BY", pid, wiki_url, f"Starring: {a}", "infobox_metadata")

        # 3. Biên kịch (WRITTEN_BY) từ metadata
        writers = [w.strip() for w in str(row.get("writer", "")).split(" ; ") if w.strip()]
        for w in writers:
            pid = add_entity("Person", w)
            add_relation(movie_eid, "WRITTEN_BY", pid, wiki_url, f"Writer: {w}", "infobox_metadata")

        # 4. Nhà sản xuất / Hãng phim (PRODUCED_BY) từ metadata
        producers = [p.strip() for p in str(row.get("producer", "")).split(" ; ") if p.strip()]
        for p in producers:
            pid = add_entity("Person", p)
            add_relation(movie_eid, "PRODUCED_BY", pid, wiki_url, f"Producer: {p}", "infobox_metadata")

        companies = [c.strip() for c in str(row.get("production_company", "")).split(" ; ") if c.strip()]
        for c in companies:
            oid = add_entity("Organization", c)
            add_relation(movie_eid, "PRODUCED_BY", oid, wiki_url, f"Production company: {c}", "infobox_metadata")

        # 5. Thể loại (HAS_GENRE) từ metadata
        genres = [g.strip() for g in str(row.get("genre", "")).split(" ; ") if g.strip()]
        for g in genres:
            gid = add_entity("Genre", g)
            add_relation(movie_eid, "HAS_GENRE", gid, wiki_url, f"Genre: {g}", "infobox_metadata")

        # 6. Quốc gia (PRODUCED_IN) từ metadata
        countries = [c.strip() for c in str(row.get("country", "")).split(" ; ") if c.strip()]
        for c in countries:
            cid = add_entity("Country", c)
            add_relation(movie_eid, "PRODUCED_IN", cid, wiki_url, f"Country: {c}", "infobox_metadata")

        # 7. Ngôn ngữ (IN_LANGUAGE) từ metadata
        languages = [l.strip() for l in str(row.get("language", "")).split(" ; ") if l.strip()]
        for l in languages:
            lid = add_entity("Language", l)
            add_relation(movie_eid, "IN_LANGUAGE", lid, wiki_url, f"Language: {l}", "infobox_metadata")

        # --- NLP & Rule-based text extraction nếu thiếu đạo diễn/diễn viên từ metadata ---
        if content and (len(directors) == 0 or len(actors) == 0):
            # Quy tắc regex cho "directed by [Name]"
            if len(directors) == 0:
                m_dir = re.search(r'directed\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', content)
                if m_dir:
                    d_name = m_dir.group(1).strip()
                    pid = add_entity("Person", d_name)
                    add_relation(movie_eid, "DIRECTED_BY", pid, wiki_url, m_dir.group(0), "nlp_text_extraction")

            # Quy tắc regex cho "starring [Name1] and [Name2]"
            if len(actors) == 0:
                m_star = re.search(r'starring\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', content)
                if m_star:
                    a_name = m_star.group(1).strip()
                    pid = add_entity("Person", a_name)
                    add_relation(movie_eid, "ACTED_BY", pid, wiki_url, m_star.group(0), "nlp_text_extraction")

    # Lưu entities ra CSV
    df_entities = pd.DataFrame(list(entities.values()))
    df_entities.sort_values(by=["entity_type", "entity_name"], inplace=True)
    df_entities.to_csv(entities_file, index=False, encoding="utf-8-sig")
    logger.info(f"Đã lưu {len(df_entities)} thực thể vào: {entities_file}")

    # Thống kê số lượng thực thể theo loại
    logger.info("=== Phân bố thực thể theo loại ===")
    for etype, count in df_entities["entity_type"].value_counts().items():
        logger.info(f" - {etype:15s}: {count:6d}")

    # Lưu relations ra CSV
    df_relations = pd.DataFrame(relations)
    df_relations.sort_values(by=["relation_type", "source_id"], inplace=True)
    df_relations.to_csv(relations_file, index=False, encoding="utf-8-sig")
    logger.info(f"Đã lưu {len(df_relations)} quan hệ vào: {relations_file}")

    # Thống kê số lượng quan hệ theo loại
    logger.info("=== Phân bố quan hệ theo loại ===")
    for rtype, count in df_relations["relation_type"].value_counts().items():
        logger.info(f" - {rtype:15s}: {count:6d}")

    # Thống kê phương thức trích xuất
    logger.info("=== Phương thức trích xuất ===")
    for method, count in df_relations["extraction_method"].value_counts().items():
        logger.info(f" - {method:20s}: {count:6d}")

    return df_entities, df_relations


def main():
    parser = argparse.ArgumentParser(description="Trích xuất thực thể và quan hệ từ movies.csv")
    parser.add_argument("--input", type=str, default=None, help="Đường dẫn file movies csv đã xử lý")
    parser.add_argument("--entities", type=str, default=None, help="Đường dẫn output entities csv")
    parser.add_argument("--relations", type=str, default=None, help="Đường dẫn output relations csv")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else INPUT_MOVIES_CSV
    entities_path = Path(args.entities) if args.entities else ENTITIES_CSV
    relations_path = Path(args.relations) if args.relations else RELATIONS_CSV

    if not input_path.exists():
        logger.error(f"Không tìm thấy file movies: {input_path}")
        return

    df_movies = pd.read_csv(input_path)
    extract_entities_and_relations(df_movies, entities_path, relations_path)


if __name__ == "__main__":
    main()
