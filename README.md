# Thu Thập Dữ Liệu 5.000 Phim Điện Ảnh từ Wikipedia, Trích Xuất Thực Thể, Mối Quan Hệ và Thống Kê Cơ Bản

Dự án kỹ thuật dữ liệu (Data Engineering & NLP Pipeline) thực hiện thu thập tự động 5.000 bài viết phim điện ảnh phát hành trong giai đoạn **2015 – 2025** từ Wikipedia & Wikidata, làm sạch và chuẩn hóa dữ liệu, trích xuất mạng thực thể - quan hệ ngữ nghĩa (Knowledge Graph Triplet), và trực quan hóa thống kê mô tả.

---

## 1. Cấu Trúc Thư Mục Dự Án

```text
film/
├── data/
│   ├── raw/                           # Dữ liệu gốc và nhật ký thu thập
│   │   ├── movie_candidates.json      # 5.200 ứng viên phim (tên, QID, URL, năm)
│   │   ├── raw_movies.jsonl           # Dữ liệu thô crawl từ Wikipedia (dạng stream JSONL)
│   │   └── crawl_log.csv              # Nhật ký trạng thái crawl từng trang
│   ├── processed/                     # Dữ liệu sạch sau tiền xử lý
│   │   ├── movies.csv                 # 5.000 phim với đầy đủ 15 trường thông tin
│   │   ├── entities.csv               # Danh sách thực thể (Movie, Person, Genre, Org, Country, Language)
│   │   └── relations.csv              # Mối quan hệ giữa các thực thể (7 loại quan hệ)
│   └── results/                       # Kết quả thống kê và biểu đồ trực quan hóa
│       ├── statistics.json            # Chỉ số thống kê định dạng JSON
│       ├── statistics.csv             # Bảng chỉ số thống kê định dạng CSV
│       ├── 01_movies_per_year.png     # Biểu đồ số lượng phim theo năm (2015-2025)
│       ├── 02_top_genres.png          # Biểu đồ Top 10 thể loại phổ biến nhất
│       ├── 03_top_directors.png       # Biểu đồ Top 10 đạo diễn xuất hiện nhiều nhất
│       ├── 04_top_actors.png          # Biểu đồ Top 10 diễn viên xuất hiện nhiều nhất
│       ├── 05_top_countries.png       # Biểu đồ Top 10 quốc gia sản xuất phim
│       ├── 06_runtime_distribution.png# Biểu đồ phân bố thời lượng phim
│       ├── 07_entities_count.png      # Biểu đồ số lượng thực thể theo loại
│       ├── 08_relations_count.png     # Biểu đồ số lượng quan hệ theo loại
│       ├── 09_missing_data_rate.png   # Biểu đồ tỷ lệ dữ liệu thiếu theo trường
│       └── 10_crawl_status.png        # Biểu đồ tỷ lệ crawl thành công / thất bại
├── notebooks/
│   └── analysis.ipynb                 # Jupyter Notebook phân tích & trực quan hóa
├── src/
│   ├── collect_movies.py              # Bước 1: Thu thập danh sách ứng viên từ Wikipedia & Wikidata
│   ├── crawl_wikipedia.py             # Bước 2: Crawl nội dung, infobox wikitext và lead extract
│   ├── preprocess.py                  # Bước 3: Tiền xử lý, chuẩn hóa, deduplicate, tạo movies.csv
│   ├── extract_entities_relations.py  # Bước 4: Trích xuất thực thể và quan hệ
│   └── analyze.py                     # Bước 5: Thống kê mô tả và xuất 10 biểu đồ
├── requirements.txt                   # Danh sách thư viện Python cần thiết
├── REPORT.md                          # Báo cáo tổng kết phương pháp và kết quả
└── README.md                          # Hướng dẫn chi tiết
```

---

## 2. Công Nghệ & Thư Viện

Dự án chỉ sử dụng Python và các thư viện mã nguồn mở tiêu chuẩn, không phụ thuộc vào cơ sở dữ liệu đồ thị phức tạp (Neo4j), backend hay Docker:
- **`requests`**: Gọi API có cấu trúc từ Wikipedia MediaWiki API và Wikidata pageprops.
- **`mwparserfromhell`**: Phân tích cú pháp Wikitext chuyên sâu để bóc tách `{{Infobox film}}`, wikilinks, template danh sách (`ubl`, `plainlist`, `flatlist`, `Film date`).
- **`pandas`, `numpy`**: Xử lý bảng dữ liệu, chuẩn hóa, lọc trùng lặp và tính toán thống kê mô tả.
- **`spacy`**: Nhận diện thực thể và bóc tách quan hệ bổ trợ từ văn bản mở đầu (`en_core_web_sm`).
- **`matplotlib`, `seaborn`**: Thiết kế và vẽ 10 biểu đồ trực quan hóa dữ liệu chất lượng cao (300 DPI).
- **`tqdm`**: Thanh tiến độ trực quan trong quá trình crawl.

---

## 3. Các Trường Dữ Liệu Thu Thập (`movies.csv`)

| Tên trường | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `movie_id` | Chuỗi | Định danh duy nhất từ Wikidata (ví dụ: `Q23781155`) hoặc mã Wikipedia |
| `title` | Chuỗi | Tên phim đã được làm sạch, bỏ hậu tố định hướng `(film)` |
| `release_year`| Số nguyên | Năm phát hành trong khoảng `2015 – 2025` |
| `release_date`| Chuỗi | Ngày phát hành đầy đủ theo chuẩn ISO `YYYY-MM-DD` hoặc `YYYY` |
| `director` | Chuỗi | Danh sách đạo diễn, phân cách bởi ` ; ` |
| `cast` | Chuỗi | Danh sách diễn viên chính, phân cách bởi ` ; ` |
| `writer` | Chuỗi | Danh sách biên kịch / kịch bản, phân cách bởi ` ; ` |
| `producer` | Chuỗi | Danh sách nhà sản xuất cá nhân, phân cách bởi ` ; ` |
| `production_company` | Chuỗi | Hãng phim, xưởng phim, đơn vị phân phối, phân cách bởi ` ; ` |
| `genre` | Chuỗi | Thể loại phim (Action, Drama, Comedy,...), phân cách bởi ` ; ` |
| `country` | Chuỗi | Quốc gia sản xuất, phân cách bởi ` ; ` |
| `language` | Chuỗi | Ngôn ngữ gốc của phim, phân cách bởi ` ; ` |
| `runtime` | Số thực | Thời lượng tính theo phút (ví dụ: 181.0) |
| `wiki_url` | Chuỗi | Đường dẫn bài viết Wikipedia tương ứng |
| `content` | Chuỗi | Đoạn tóm tắt văn bản dẫn nhập sạch của bài viết |

---

## 4. Các Loại Thực Thể & Quan Hệ Ngữ Nghĩa

### 4.1 Thực thể (`entities.csv`)
1. **`Movie`**: Phim điện ảnh (`MOV_...` hoặc QID).
2. **`Person`**: Đạo diễn, diễn viên, biên kịch, nhà sản xuất (`PER_...`).
3. **`Genre`**: Thể loại phim (`GEN_...`).
4. **`Organization`**: Hãng phim, công ty phát hành (`ORG_...`).
5. **`Country`**: Quốc gia sản xuất (`COU_...`).
6. **`Language`**: Ngôn ngữ gốc (`LAN_...`).

### 4.2 Quan hệ (`relations.csv`)
1. **`DIRECTED_BY`**: Movie $\rightarrow$ Person (Đạo diễn).
2. **`ACTED_BY`**: Movie $\rightarrow$ Person (Diễn viên).
3. **`WRITTEN_BY`**: Movie $\rightarrow$ Person (Biên kịch).
4. **`PRODUCED_BY`**: Movie $\rightarrow$ Person / Organization (Nhà sản xuất / Hãng phim).
5. **`HAS_GENRE`**: Movie $\rightarrow$ Genre (Thể loại).
6. **`PRODUCED_IN`**: Movie $\rightarrow$ Country (Quốc gia sản xuất).
7. **`IN_LANGUAGE`**: Movie $\rightarrow$ Language (Ngôn ngữ).

*Mỗi quan hệ lưu kèm `evidence_text` (câu văn/dòng thông tin làm bằng chứng) và `extraction_method` (`infobox_metadata` hoặc `nlp_text_extraction`).*

---

## 5. Hướng Dẫn Cài Đặt & Chạy Pipeline

### Bước 1: Khởi tạo môi trường ảo và cài đặt thư viện
```bash
# Di chuyển vào thư mục film
cd film

# Tạo virtualenv
python -m venv .venv

# Kích hoạt virtualenv:
# Trên Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Trên Linux/macOS:
# source .venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt

# Tải mô hình ngôn ngữ spaCy
python -m spacy download en_core_web_sm
```

### Bước 2: Chạy thu thập danh sách ứng viên (5.200 phim)
```bash
python src/collect_movies.py --target 5200
```
*Tạo file `data/raw/movie_candidates.json` chứa 5.200 phim ứng viên kèm Wikidata QID.*

### Bước 3: Chạy crawl nội dung Wikipedia và phân tích Infobox
```bash
python src/crawl_wikipedia.py --batch_size 20
```
*Hỗ trợ checkpointing: nếu bị gián đoạn, chỉ cần chạy lại lệnh trên, chương trình sẽ tự động bỏ qua các bài viết đã tải và crawl tiếp.*

### Bước 4: Tiền xử lý, lọc trùng lặp và chuẩn hóa
```bash
python src/preprocess.py
```
*Tạo file `data/processed/movies.csv` đạt chuẩn 5.000 phim.*

### Bước 5: Trích xuất thực thể và quan hệ
```bash
python src/extract_entities_relations.py
```
*Tạo 2 file: `data/processed/entities.csv` và `data/processed/relations.csv`.*

### Bước 6: Thống kê mô tả và xuất 10 biểu đồ trực quan
```bash
python src/analyze.py
```
*Tạo 10 biểu đồ PNG sắc nét trong `data/results/`, xuất `statistics.json` và `statistics.csv`.*

### Bước 7: Khám phá bằng Jupyter Notebook
```bash
jupyter notebook notebooks/analysis.ipynb
```

---

## 6. Tính Năng Kỹ Thuật Nổi Bật
- **Không hard-code:** Dữ liệu hoàn toàn được phát hiện động qua Wikipedia Category Members API và Wikidata pageprops.
- **Khả năng phục hồi (Resilience & Checkpoint):** Lưu dạng stream JSON Lines (`raw_movies.jsonl`), có thể dừng và tiếp tục bất kỳ lúc nào mà không bị mất dữ liệu hay crawl trùng.
- **Batch Processing:** Nhóm 15–20 tiêu đề mỗi request API, giảm từ 5.000 lượt gọi mạng xuống ~260 lượt, tăng tốc độ gấp 15 lần mà không bị rate limit.
- **Xử lý Wikitext thông minh:** Tự động chuẩn hóa HTML breaks (`<br>`), unbulleted lists, wikilinks, template ngày tháng `Film date`, xử lý ngoại lệ triệt để.
