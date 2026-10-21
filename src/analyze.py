"""
Module: analyze.py
Description: Thực hiện thống kê mô tả, tính toán các chỉ số và trực quan hóa bằng biểu đồ đẹp mắt.
Author: Data Engineering Team
"""

import os
import json
import logging
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("Analyze")

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
RAW_DIR = BASE_DIR / "data" / "raw"
RESULTS_DIR = BASE_DIR / "data" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Cấu hình phong cách biểu đồ Seaborn/Matplotlib hiện đại
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.labelsize": 12,
    "figure.titlesize": 16,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight"
})


def analyze_and_plot(movies_file: Path, entities_file: Path, relations_file: Path, log_file: Path, results_dir: Path):
    """
    Thực hiện 10 phân tích thống kê và vẽ 10 biểu đồ trực quan theo đúng yêu cầu đề tài.
    """
    logger.info("Đang đọc dữ liệu cho phân tích thống kê...")
    df_movies = pd.read_csv(movies_file)
    df_entities = pd.read_csv(entities_file)
    df_relations = pd.read_csv(relations_file)
    df_log = pd.read_csv(log_file) if log_file.exists() else pd.DataFrame()

    total_movies = len(df_movies)
    logger.info(f"Tổng số phim: {total_movies}, Thực thể: {len(df_entities)}, Quan hệ: {len(df_relations)}")

    stats_summary = {}

    # -------------------------------------------------------------
    # 1. Số lượng phim theo năm phát hành
    # -------------------------------------------------------------
    logger.info("1. Phân tích số lượng phim theo năm phát hành...")
    year_counts = df_movies["release_year"].value_counts().sort_index()
    stats_summary["movies_per_year"] = year_counts.to_dict()

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(year_counts.index.astype(str), year_counts.values, color="#3b82f6", edgecolor="#1d4ed8", width=0.6)
    for bar in bars:
        h = bar.get_height()
        ax.annotate(f"{int(h)}",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_title("1. Số lượng phim theo năm phát hành (2015 – 2025)")
    ax.set_xlabel("Năm phát hành")
    ax.set_ylabel("Số lượng phim")
    plt.tight_layout()
    plt.savefig(results_dir / "01_movies_per_year.png")
    plt.close()

    # -------------------------------------------------------------
    # 2. Top 10 thể loại phổ biến nhất
    # -------------------------------------------------------------
    logger.info("2. Phân tích Top 10 thể loại...")
    genre_series = df_movies["genre"].dropna().apply(lambda x: [g.strip() for g in str(x).split(" ; ") if g.strip()])
    all_genres = [g for sublist in genre_series for g in sublist]
    top_genres = pd.Series(all_genres).value_counts().head(10)
    stats_summary["top_10_genres"] = top_genres.to_dict()

    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.barplot(x=top_genres.values, y=top_genres.index, hue=top_genres.index, legend=False, ax=ax, palette="mako")
    for i, v in enumerate(top_genres.values):
        ax.text(v + (max(top_genres.values) * 0.01), i, f"{v}", va="center", fontweight="bold")
    ax.set_title("2. Top 10 Thể loại phim phổ biến nhất")
    ax.set_xlabel("Số lượng phim")
    ax.set_ylabel("Thể loại")
    plt.tight_layout()
    plt.savefig(results_dir / "02_top_genres.png")
    plt.close()

    # -------------------------------------------------------------
    # 3. Top 10 đạo diễn xuất hiện nhiều nhất
    # -------------------------------------------------------------
    logger.info("3. Phân tích Top 10 đạo diễn...")
    dir_series = df_movies["director"].dropna().apply(lambda x: [d.strip() for d in str(x).split(" ; ") if d.strip()])
    all_directors = [d for sublist in dir_series for d in sublist]
    top_directors = pd.Series(all_directors).value_counts().head(10)
    stats_summary["top_10_directors"] = top_directors.to_dict()

    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.barplot(x=top_directors.values, y=top_directors.index, hue=top_directors.index, legend=False, ax=ax, palette="crest")
    for i, v in enumerate(top_directors.values):
        ax.text(v + (max(top_directors.values) * 0.01), i, f"{v}", va="center", fontweight="bold")
    ax.set_title("3. Top 10 Đạo diễn xuất hiện nhiều nhất")
    ax.set_xlabel("Số lượng phim tham gia chỉ đạo")
    ax.set_ylabel("Đạo diễn")
    plt.tight_layout()
    plt.savefig(results_dir / "03_top_directors.png")
    plt.close()

    # -------------------------------------------------------------
    # 4. Top 10 diễn viên xuất hiện nhiều nhất
    # -------------------------------------------------------------
    logger.info("4. Phân tích Top 10 diễn viên...")
    cast_series = df_movies["cast"].dropna().apply(lambda x: [a.strip() for a in str(x).split(" ; ") if a.strip()])
    all_actors = [a for sublist in cast_series for a in sublist]
    top_actors = pd.Series(all_actors).value_counts().head(10)
    stats_summary["top_10_actors"] = top_actors.to_dict()

    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.barplot(x=top_actors.values, y=top_actors.index, hue=top_actors.index, legend=False, ax=ax, palette="viridis")
    for i, v in enumerate(top_actors.values):
        ax.text(v + (max(top_actors.values) * 0.01), i, f"{v}", va="center", fontweight="bold")
    ax.set_title("4. Top 10 Diễn viên xuất hiện nhiều nhất")
    ax.set_xlabel("Số lượng phim tham gia đóng")
    ax.set_ylabel("Diễn viên")
    plt.tight_layout()
    plt.savefig(results_dir / "04_top_actors.png")
    plt.close()

    # -------------------------------------------------------------
    # 5. Phân bố phim theo quốc gia sản xuất
    # -------------------------------------------------------------
    logger.info("5. Phân tích phân bố phim theo quốc gia...")
    country_series = df_movies["country"].dropna().apply(lambda x: [c.strip() for c in str(x).split(" ; ") if c.strip()])
    all_countries = [c for sublist in country_series for c in sublist]
    top_countries = pd.Series(all_countries).value_counts().head(10)
    stats_summary["top_10_countries"] = top_countries.to_dict()

    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.barplot(x=top_countries.values, y=top_countries.index, hue=top_countries.index, legend=False, ax=ax, palette="magma")
    for i, v in enumerate(top_countries.values):
        ax.text(v + (max(top_countries.values) * 0.01), i, f"{v}", va="center", fontweight="bold")
    ax.set_title("5. Top 10 Quốc gia sản xuất nhiều phim nhất")
    ax.set_xlabel("Số lượng phim")
    ax.set_ylabel("Quốc gia")
    plt.tight_layout()
    plt.savefig(results_dir / "05_top_countries.png")
    plt.close()

    # -------------------------------------------------------------
    # 6. Thời lượng trung bình, trung vị và phân bố thời lượng
    # -------------------------------------------------------------
    logger.info("6. Phân tích thời lượng phim...")
    runtimes = df_movies["runtime"].dropna()
    mean_rt = runtimes.mean()
    median_rt = runtimes.median()
    std_rt = runtimes.std()
    min_rt = runtimes.min()
    max_rt = runtimes.max()
    stats_summary["runtime_statistics"] = {
        "mean_minutes": round(float(mean_rt), 2) if not np.isnan(mean_rt) else None,
        "median_minutes": float(median_rt) if not np.isnan(median_rt) else None,
        "std_minutes": round(float(std_rt), 2) if not np.isnan(std_rt) else None,
        "min_minutes": float(min_rt) if not np.isnan(min_rt) else None,
        "max_minutes": float(max_rt) if not np.isnan(max_rt) else None,
        "valid_count": int(len(runtimes))
    }

    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.histplot(runtimes, kde=True, color="#059669", bins=25, ax=ax)
    ax.axvline(mean_rt, color="#dc2626", linestyle="--", linewidth=2, label=f"Trung bình: {mean_rt:.1f} phút")
    ax.axvline(median_rt, color="#d97706", linestyle="-.", linewidth=2, label=f"Trung vị: {median_rt:.1f} phút")
    ax.set_title("6. Phân bố thời lượng phim (Runtime Distribution)")
    ax.set_xlabel("Thời lượng (phút)")
    ax.set_ylabel("Tần suất (Số phim)")
    ax.legend(frameon=True)
    plt.tight_layout()
    plt.savefig(results_dir / "06_runtime_distribution.png")
    plt.close()

    # -------------------------------------------------------------
    # 7. Số lượng thực thể theo từng loại
    # -------------------------------------------------------------
    logger.info("7. Thống kê thực thể theo loại...")
    entity_counts = df_entities["entity_type"].value_counts()
    stats_summary["entities_by_type"] = entity_counts.to_dict()

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(entity_counts.index, entity_counts.values, color="#6366f1", edgecolor="#4338ca", width=0.55)
    for bar in bars:
        h = bar.get_height()
        ax.annotate(f"{int(h):,}",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_title("7. Số lượng thực thể theo từng loại (Entities by Type)")
    ax.set_xlabel("Loại thực thể")
    ax.set_ylabel("Số lượng thực thể")
    plt.tight_layout()
    plt.savefig(results_dir / "07_entities_count.png")
    plt.close()

    # -------------------------------------------------------------
    # 8. Tổng số quan hệ đã trích xuất theo loại
    # -------------------------------------------------------------
    logger.info("8. Thống kê quan hệ theo loại...")
    rel_counts = df_relations["relation_type"].value_counts()
    stats_summary["relations_by_type"] = rel_counts.to_dict()

    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.barplot(x=rel_counts.values, y=rel_counts.index, hue=rel_counts.index, legend=False, ax=ax, palette="rocket")
    for i, v in enumerate(rel_counts.values):
        ax.text(v + (max(rel_counts.values) * 0.01), i, f"{v:,}", va="center", fontweight="bold")
    ax.set_title("8. Tổng số quan hệ đã trích xuất theo loại (Relations by Type)")
    ax.set_xlabel("Số lượng quan hệ")
    ax.set_ylabel("Loại quan hệ")
    plt.tight_layout()
    plt.savefig(results_dir / "08_relations_count.png")
    plt.close()

    # -------------------------------------------------------------
    # 9. Tỷ lệ dữ liệu thiếu theo từng trường
    # -------------------------------------------------------------
    logger.info("9. Thống kê tỷ lệ dữ liệu thiếu...")
    missing_rates = {}
    for col in df_movies.columns:
        if col == "runtime":
            m_count = df_movies[col].isna().sum()
        else:
            m_count = ((df_movies[col] == "") | df_movies[col].isna()).sum()
        missing_rates[col] = round((m_count / total_movies) * 100, 2)
    stats_summary["missing_data_pct"] = missing_rates

    sr_missing = pd.Series(missing_rates).sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(x=sr_missing.values, y=sr_missing.index, hue=sr_missing.index, legend=False, ax=ax, palette="YlOrRd_r")
    for i, v in enumerate(sr_missing.values):
        ax.text(v + 0.5, i, f"{v:.1f}%", va="center", fontsize=9, fontweight="bold")
    ax.set_title("9. Tỷ lệ thiếu dữ liệu theo trường thông tin (%)")
    ax.set_xlabel("Tỷ lệ thiếu (%)")
    ax.set_ylabel("Trường thông tin")
    ax.set_xlim(0, max(sr_missing.values) + 10)
    plt.tight_layout()
    plt.savefig(results_dir / "09_missing_data_rate.png")
    plt.close()

    # -------------------------------------------------------------
    # 10. Số trang crawl thành công và thất bại
    # -------------------------------------------------------------
    logger.info("10. Thống kê trạng thái crawl...")
    if not df_log.empty and "status" in df_log.columns:
        crawl_status = df_log["status"].value_counts()
    else:
        crawl_status = pd.Series({"SUCCESS": total_movies, "FAILED": 0})
    stats_summary["crawl_status"] = crawl_status.to_dict()

    fig, ax = plt.subplots(figsize=(7, 5))
    colors = ["#10b981", "#ef4444"] if len(crawl_status) == 2 else ["#10b981"]
    wedges, texts, autotexts = ax.pie(
        crawl_status.values,
        labels=crawl_status.index,
        autopct="%1.1f%%",
        startangle=140,
        colors=colors,
        textprops=dict(color="black", fontweight="bold")
    )
    ax.set_title("10. Tỷ lệ crawl thành công vs thất bại")
    plt.tight_layout()
    plt.savefig(results_dir / "10_crawl_status.png")
    plt.close()

    # Xuất file thống kê statistics.json và statistics.csv
    with open(results_dir / "statistics.json", "w", encoding="utf-8") as f:
        json.dump(stats_summary, f, ensure_ascii=False, indent=2)
    logger.info(f"Đã lưu thống kê vào: {results_dir / 'statistics.json'}")

    # Chuyển đổi một số bảng chỉ số ra statistics.csv
    flat_rows = []
    for k, v in stats_summary.items():
        if isinstance(v, dict):
            for sub_k, sub_v in v.items():
                flat_rows.append({"category": k, "metric": str(sub_k), "value": sub_v})
        else:
            flat_rows.append({"category": k, "metric": "total", "value": v})
    pd.DataFrame(flat_rows).to_csv(results_dir / "statistics.csv", index=False, encoding="utf-8-sig")
    logger.info(f"Đã lưu bảng thống kê vào: {results_dir / 'statistics.csv'}")

    logger.info("Quá trình phân tích thống kê và vẽ biểu đồ đã hoàn thành 100%!")


def main():
    parser = argparse.ArgumentParser(description="Thực hiện phân tích thống kê và vẽ biểu đồ")
    parser.add_argument("--movies", type=str, default=None, help="Đường dẫn file movies.csv")
    parser.add_argument("--entities", type=str, default=None, help="Đường dẫn file entities.csv")
    parser.add_argument("--relations", type=str, default=None, help="Đường dẫn file relations.csv")
    parser.add_argument("--log", type=str, default=None, help="Đường dẫn file crawl_log.csv")
    parser.add_argument("--results", type=str, default=None, help="Thư mục lưu biểu đồ và thống kê")
    args = parser.parse_args()

    movies_path = Path(args.movies) if args.movies else PROCESSED_DIR / "movies.csv"
    entities_path = Path(args.entities) if args.entities else PROCESSED_DIR / "entities.csv"
    relations_path = Path(args.relations) if args.relations else PROCESSED_DIR / "relations.csv"
    log_path = Path(args.log) if args.log else RAW_DIR / "crawl_log.csv"
    results_path = Path(args.results) if args.results else RESULTS_DIR

    if not movies_path.exists() or not entities_path.exists() or not relations_path.exists():
        logger.error("Chưa có đủ các file CSV đã xử lý để phân tích!")
        return

    analyze_and_plot(movies_path, entities_path, relations_path, log_path, results_path)


if __name__ == "__main__":
    main()
