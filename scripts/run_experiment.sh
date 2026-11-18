#!/usr/bin/env bash
# ==============================================================================
# Quy trình tự động hóa toàn bộ thí nghiệm tìm giá trị CUTOFF tối ưu cho Mergesort
# Cấu trúc quy trình:
#   Bước 1: Biên dịch mã nguồn Java (MergeSort, DatasetGenerator, BenchmarkRunner, CostModelAnalyzer)
#   Bước 2: Sinh bộ dữ liệu thí nghiệm chuẩn hóa cố định seed (nếu chưa có)
#   Bước 3: Chạy phân tích Mô hình Chi phí (Cost Model - Chủ đề 1.3)
#   Bước 4: Chạy đo thời gian thực nghiệm (JVM Warm-up + Thiết kế khối ngẫu nhiên RCBD)
#   Bước 5: Phân tích thống kê (Mean, SD, 95% CI, Paired t-test) và xuất đồ thị 300 DPI
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/5] Biên dịch mã nguồn Java..."
mkdir -p bin results/figures
javac -Xlint:deprecation -d bin src/*.java

if [ ! -f "datasets/manifest.csv" ]; then
    echo "[2/5] Sinh bộ dữ liệu thí nghiệm cố định seed..."
    java -cp bin DatasetGenerator datasets
else
    echo "[2/5] Bộ dữ liệu thí nghiệm đã sẵn sàng tại datasets/ (bỏ qua bước sinh lại)."
fi

echo "[3/5] Phân tích Mô hình Chi phí (Cost Model)..."
java -Xms1g -Xmx3g -cp bin CostModelAnalyzer datasets results/cost_model_counts.csv

echo "[4/5] Chạy đo thời gian thực nghiệm trên phần cứng hiện tại..."
java -Xms4g -Xmx6g -XX:+AlwaysPreTouch -cp bin BenchmarkRunner datasets results/raw_measurements.csv results/primitive_vs_comparable.csv

echo "[5/5] Thống kê kết quả và vẽ đồ thị khoa học..."
python3 scripts/analyze_and_plot.py

echo "=== HOÀN TẤT TOÀN BỘ QUY TRÌNH THÍ NGHIỆM ==="
