# Thí Nghiệm Xác Định Giá Trị `CUTOFF` Tối Ưu Cho Thuật Toán Mergesort

- **Sinh viên thực hiện:** Nguyễn Bảo Đăng — **MSV:** `25020115` — **Lớp:** `IT1-K70`
- **Học phần:** Cấu trúc dữ liệu và Giải thuật (Chủ đề 1.3 *Algorithm Analysis* & Chủ đề 2.2 *Mergesort*)

Dự án thực nghiệm phân tích hiệu năng thuật toán theo **Chủ đề 1.3. Algorithm Analysis** và **Chủ đề 2.2. Mergesort** (giáo trình *Algorithms, 4th Edition* — Robert Sedgewick & Kevin Wayne) trên cấu hình máy **Apple M4 (macOS arm64, Oracle JDK 25 LTS)**.

---

## 1. Cấu trúc thư mục dự án

```text
mergesort-cutoff-experiment/
├── report/                                         # [1] BÁO CÁO THÍ NGHIỆM (3 định dạng)
│   ├── Bao_Cao_Thi_Nghiem_MergeSort_CUTOFF.pdf     # Bản PDF trình bày chuẩn in ấn (đính kèm 6 đồ thị 300 DPI)
│   ├── Bao_Cao_Thi_Nghiem_MergeSort_CUTOFF.docx    # Bản Word (.docx) đầy đủ nội dung & đồ thị nhúng
│   └── Bao_Cao_Thi_Nghiem_MergeSort_CUTOFF.md      # Bản gốc Markdown
│
├── src/                                            # [2a] CÀI ĐẶT MERGESORT & MÃ NGUỒN ĐO THỰC NGHIỆM
│   ├── MergeSort.java                              # Cài đặt Top-down Mergesort + CUTOFF chuẩn bài giảng
│   ├── DatasetGenerator.java                       # Sinh bộ dữ liệu kiểm thử cố định seed & mã băm SHA-256
│   ├── BenchmarkRunner.java                        # Đo thời gian chạy (JVM Warm-up + Thiết kế khối RCBD)
│   └── CostModelAnalyzer.java                      # Đếm số phép so sánh, ghi mảng & lời gọi đệ quy (Cost Model)
│
├── scripts/                                        # [2b] SCRIPT TỰ ĐỘNG HÓA THÍ NGHIỆM & THỐNG KÊ ĐỒ THỊ
│   ├── run_experiment.sh                           # Script chạy tự động trọn gói từ biên dịch đến vẽ đồ thị
│   ├── analyze_and_plot.py                         # Thống kê Mean, Trimmed Mean, SD, 95% CI, t-test & xuất 6 đồ thị
│   └── build_reports.py                            # Script kết xuất báo cáo sang định dạng .docx và .pdf
│
├── datasets/                                       # [3] BỘ DỮ LIỆU THÍ NGHIỆM (14 bộ test + manifest SHA-256)
│   ├── manifest.csv                                # Bảng kê quy mô N, hạt giống seed và mã SHA-256 từng tệp
│   ├── random_N10000.txt ... random_N1000000.txt   # 11 bộ dữ liệu ngẫu nhiên đều đa quy mô [10k..1M]
│   ├── nearly_sorted_N200000.txt                   # Mảng gần sắp xếp (2% hoán đổi ngẫu nhiên)
│   ├── reverse_sorted_N200000.txt                  # Mảng sắp xếp ngược giảm dần (Worst-case Insertion Sort)
│   └── few_unique_N200000.txt                      # Mảng nhiều khóa trùng lặp (50 giá trị phân biệt)
│
└── results/                                        # SỐ LIỆU ĐO THỰC TẾ & ĐỒ THỊ KHOA HỌC
    ├── raw_measurements.csv                        # Toàn bộ dữ liệu thô từng lượt chạy (nano giây & mili giây)
    ├── summary_statistics.csv                      # Bảng tổng hợp thống kê chi tiết cho từng bộ dữ liệu
    ├── multiscale_normalized_summary.csv           # Bảng chuẩn hóa đa quy mô [100k..1M]
    ├── cost_model_counts.csv                       # Số liệu đếm phép toán theo Mô hình Chi phí
    ├── primitive_vs_comparable.csv                 # Dữ liệu đo thô đối chứng Comparable[] vs int[]
    ├── primitive_vs_comparable_summary.csv         # Bảng tổng hợp thống kê đối chứng Comparable[] vs int[]
    ├── key_findings.json                           # Tóm tắt các mốc thống kê & kiểm định t bắt cặp
    └── figures/                                    # 6 đồ thị phân tích độ phân giải cao (300 DPI PNG)
```

---

## 2. Hướng dẫn biên dịch và chạy lại thí nghiệm

Yêu cầu môi trường: **JDK 17+** (đã đo chuẩn trên **JDK 25.0.2 LTS**) và **Python 3** (`numpy`, `pandas`, `scipy`, `matplotlib`).

### Chạy tự động toàn bộ quy trình bằng 1 lệnh:
```bash
bash scripts/run_experiment.sh
```

### Hoặc chạy từng bước độc lập:
```bash
# 1. Biên dịch mã nguồn Java
mkdir -p bin
javac -Xlint:deprecation -d bin src/*.java

# 2. Sinh lại bộ dữ liệu thí nghiệm (tái lập chính xác 100% mã SHA-256)
java -cp bin DatasetGenerator datasets

# 3. Chạy thống kê Mô hình Chi phí (Cost Model)
java -Xms1g -Xmx3g -cp bin CostModelAnalyzer datasets results/cost_model_counts.csv

# 4. Chạy đo thời gian thực nghiệm (bật kiểm tra đúng đắn tự động)
java -Xms4g -Xmx6g -XX:+AlwaysPreTouch -cp bin BenchmarkRunner datasets results/raw_measurements.csv results/primitive_vs_comparable.csv

# 5. Phân tích thống kê và xuất đồ thị 300 DPI
python3 scripts/analyze_and_plot.py
```

---

## 3. Tóm tắt kết quả chính trên cấu hình Apple M4 (JDK 25)

- **`CUTOFF = 0` (Mergesort thuần túy):** Mốc chuẩn `100.00%` (`258.22 ms` tại $N = 1\,000\,000$).
- **`CUTOFF = 7` (Giáo trình bản cũ):** Thời gian chuẩn hóa đa quy mô `93.39% ± 0.84%` (cải thiện **+6.61%**, tăng tốc $1.071\times$).
- **`CUTOFF = 10` (Giáo trình bản mới):** Thời gian chuẩn hóa đa quy mô `92.07% ± 0.88%` (cải thiện **+7.93%**, tăng tốc $1.086\times$).
- **`CUTOFF = 24` (Cực tiểu kỳ vọng đa quy mô — `DEFAULT_CUTOFF`):** Thời gian chuẩn hóa `90.10% ± 0.93%` (cải thiện **+9.90%**, tăng tốc **$1.110\times$**, vượt trội có ý nghĩa thống kê với $p = 0.00014$ so với `7` và $p = 0.0113$ so với `10`).
- **Dải tối ưu cân bằng toàn diện (`CUTOFF = 18 – 24`):** Tại `CUTOFF = 18`, mảng lớn $N = 10^6$ đạt cực tiểu `229.91 ms` (cải thiện **+10.96%**) đồng thời vẫn nhanh hơn **+7.84%** ngay cả trong trường hợp xấu nhất mảng sắp xếp ngược hoàn toàn.
