# LOG TRAO ĐỔI VÀ THẢO LUẬN VỚI AI (TRỢ LÝ NGHIÊN CỨU THỰC NGHIỆM)

- **Chủ đề bài tập:** Thí nghiệm tìm giá trị `CUTOFF` dùng Insertion Sort tối ưu cho cài đặt Top-down Mergesort trên cấu hình máy cá nhân (theo Chủ đề 1.3 *Algorithm Analysis* & 2.2 *Mergesort*).
- **Thời gian thực hiện:** Ngày 06/11/2026 (16:50 – 17:40, GMT+7).
- **Nguyên tắc tuân thủ yêu cầu đề bài:**
  1. Cài đặt thuật toán sắp xếp `src/MergeSort.java` được dựng chuẩn theo nội dung bài giảng (*Algorithms, 4th Edition* — Sedgewick & Wayne: `Comparable[]`, cấp phát mảng phụ `aux[]` đúng 1 lần trước đệ quy, trộn tại chỗ trừu tượng `merge()`, điều kiện dừng `hi <= lo + cutoff - 1` chuyển sang `insertionSort()`), không sử dụng thư viện sắp xếp ngoài hay các biến thể khác ngoài phạm vi bài giảng.
  2. AI được sử dụng đúng phạm vi hướng dẫn của đề bài: **thảo luận phương pháp thực nghiệm & thống kê kết quả, xây dựng bộ dữ liệu kiểm thử (`DatasetGenerator.java`), viết script tự động chạy phép đo (`BenchmarkRunner.java`, `CostModelAnalyzer.java`, `run_experiment.sh`) và xử lý thống kê / trực quan hóa đồ thị (`analyze_and_plot.py`)**.

---

## Phiên 1 — Xác nhận yêu cầu bài toán và quy chuẩn cài đặt (16:50 – 16:53)

### [Người học]
> Hãy chuẩn bị đầy đủ thông tin và hoàn thành theo quy trình được hướng dẫn để cung cấp sản phẩm nộp *(đính kèm đề bài thí nghiệm tìm giá trị CUTOFF tốt nhất đối với cấu hình máy và cài đặt mergesort từ bài giảng)*.

### [AI — Thảo luận làm rõ thông số kỹ thuật]
Để đảm bảo sản phẩm khớp chính xác với chương trình giảng dạy trên lớp và quy định nộp bài trên hệ thống LMS/Moodle, AI đã đặt 4 câu hỏi xác nhận nhanh:
1. Ngôn ngữ lập trình chuẩn của bài giảng? $\rightarrow$ **Java** (theo giáo trình *Algorithms, 4th Edition* — Sedgewick & Wayne).
2. Biến thể Mergesort trong bài giảng? $\rightarrow$ **Top-down Mergesort chuẩn bài giảng** (cấp phát mảng phụ `aux` 1 lần + thêm `CUTOFF` sang Insertion Sort).
3. Định dạng báo cáo đầu ra? $\rightarrow$ **Đầy đủ cả Word (`.docx`), PDF (`.pdf`) và Markdown (`.md`)** kèm bảng thống kê và đồ thị 300 DPI.
4. Giới hạn dung lượng nộp bài? $\rightarrow$ **Tối ưu gói nộp `.zip` < 15 MB** phù hợp giới hạn tải lên của LMS/Moodle, đồng thời đính kèm cả bộ dữ liệu thật và script sinh dữ liệu cố định `seed` để tái lập 100%.

---

## Phiên 2 — Khảo sát cấu hình phần cứng & Thiết kế phương pháp thực nghiệm theo Chủ đề 1.3 (16:53 – 17:02)

### [Nội dung thảo luận chuyên môn]
1. **Khảo sát phần cứng thực tế:**
   - Truy vấn thông số hệ thống qua `sysctl` và `java -version`: Máy Mac `Mac16,12` chạy chip **Apple M4** (`arm64`, 10 nhân gồm 4 nhân P-core + 6 nhân E-core; bộ nhớ đệm P-core L1i = 192 KB, L1d = 128 KB, Shared L2 = 16 MB; cache line = 128 bytes; RAM 16 GB), hệ điều hành macOS 26.5.2, môi trường **Oracle JDK 25.0.2 LTS**.
2. **Phát hiện hiện tượng lượng tử hóa mảng con (*Subarray Size Quantization*) trong Top-down Mergesort:**
   - Khi thảo luận cách xây dựng bộ dữ liệu kiểm thử, AI chỉ ra bẫy phổ biến nếu chỉ đo trên một kích thước $N$ duy nhất (ví dụ chỉ đo $N = 10^6$ hoặc $N = 2^{20}$): phép chia đôi liên tiếp `mid = lo + (hi - lo) / 2` khiến các mảng con ở tầng độ sâu $d$ chỉ nhận giá trị quanh $N / 2^d$. Chẳng hạn với $N = 1\,000\,000$, các tầng cuối có độ dài mảng con $\{30, 31\} \to \{15, 16\} \to \{7, 8\}$, dẫn tới mọi mức `CUTOFF` từ `8` đến `14` thực thi cây đệ quy giống hệt nhau!
   - **Giải pháp thiết kế bộ dữ liệu (`DatasetGenerator.java`):** Xây dựng 14 tệp dữ liệu cố định `seed` (kèm mã kiểm tra `SHA-256` trong `datasets/manifest.csv`), bao gồm:
     - **9 quy mô ngẫu nhiên đều từ $100\,000$ đến $1\,000\,000$** (cộng thêm $10\,000$ và $50\,000$) có phần lẻ của $\log_2(N)$ phân bố đều trên $[0, 1)$, giúp ranh giới mảng con quét kín mọi số nguyên liên tiếp từ $4$ đến $32$.
     - **3 phân phối đặc biệt tại $N = 200\,000$:** `nearly_sorted` (gần sắp xếp, 2% tráo đổi), `reverse_sorted` (giảm dần ngặt — trường hợp xấu nhất của Insertion Sort), và `few_unique` (nhiều phần tử trùng lặp, 50 khóa).
3. **Thiết kế script đo lường chuẩn Chủ đề 1.3 (`BenchmarkRunner.java` & `CostModelAnalyzer.java`):**
   - Tách riêng bộ đếm phép toán (`CostModelAnalyzer.java`: đếm số phép so sánh `less()`, số phép ghi mảng, số lời gọi đệ quy) khỏi mã `MergeSort.java` để không gây nhiễu thời gian chạy.
   - Áp dụng **JVM Warm-up** (80 lượt làm nóng cho trình biên dịch JIT HotSpot C2), **Thiết kế khối ngẫu nhiên đầy đủ (RCBD)** (xáo trộn ngẫu nhiên thứ tự 45 mức `CUTOFF` trong mỗi lượt đo để khử trôi nhiệt), cấp phát đối tượng `Integer` trung lập địa chỉ heap, chống loại bỏ mã chết bằng `volatile blackholeChecksum` và kiểm tra tự động `isSorted()` đối chiếu `Arrays.sort()`.
   - Bổ sung thực nghiệm đối chứng giữa `Comparable[]` (`Integer[]` chuẩn bài giảng) và mảng nguyên thủy `int[]` để giải thích bản chất chi phí tham chiếu con trỏ trên JVM.

---

## Phiên 3 — Chạy thử nghiệm lượt 1, Phát hiện nhiễu GC và Tinh chỉnh kỹ thuật (17:02 – 17:34)

### [Quan sát kết quả lượt đo 1 & Hiệu chỉnh]
- Ở lượt chạy đầu tiên với cấu hình heap `-Xms2g -Xmx4g` không thu gom rác giữa các khối lặp, dữ liệu thô tại mảng lớn nhất $N = 1\,000\,000$ xuất hiện một vài đỉnh nhiễu ngoại lai cục bộ (ví dụ tại `cutoff = 33`, một lượt đo bị tạm dừng bởi chu kỳ thu gom rác G1GC làm thời gian vọt lên `407.8 ms` trong khi trung vị là `226.1 ms`).
- **Quyết định cải tiến quy trình đo:**
  1. Nâng cấu hình vùng nhớ JVM lên `-Xms4g -Xmx6g -XX:+AlwaysPreTouch` để chạm sẵn trang nhớ vật lý trong RAM trước khi đo.
  2. Chủ động gọi `System.gc()` ở đầu mỗi khối RCBD (nằm **bên ngoài** cửa sổ `System.nanoTime()`) đối với các mảng lớn $N \ge 200\,000$, đảm bảo toàn bộ 45 lần cấp phát `aux[]` trong một khối ($\le 180\text{ MB}$) nằm gọn trong vùng Eden trống mà không kích hoạt bất kỳ chu kỳ GC nào trong lúc đo.
  3. Bổ sung đại lượng thống kê bền vững **10% Trimmed Mean** và **Median / IQR** bên cạnh **Mean ± 95% CI** và kiểm định **Paired Student's t-test** trong `scripts/analyze_and_plot.py`.

---

## Phiên 4 — Tổng hợp kết quả thực nghiệm cuối cùng và Đóng gói sản phẩm (17:34 – 17:45)

### [Tóm tắt phát hiện chính từ dữ liệu đo sạch nhiễu trên Apple M4 + JDK 25]
1. **So sánh các mốc giáo trình và ngưỡng tối ưu thực nghiệm:**
   - `CUTOFF = 0` (Mergesort thuần túy): Thời gian chuẩn hóa `100.00%` (`258.22 ms` tại $N = 10^6$).
   - `CUTOFF = 1`: Chậm hơn nhẹ `101.03%` do chi phí gọi hàm `insertionSort` trên nút lá kích thước 1.
   - `CUTOFF = 7` (Giáo trình cũ): Giảm **6.61%** thời gian chạy đa quy mô (tăng tốc $1.071\times$).
   - `CUTOFF = 10` (Giáo trình mới): Giảm **7.93%** thời gian chạy đa quy mô (tăng tốc $1.086\times$).
   - **`CUTOFF = 24` (Cực tiểu trung bình đa quy mô trên Apple M4):** Giảm **9.90%** thời gian chạy (`90.10% ± 0.93%`, tăng tốc **$1.110\times$**), vượt trội có ý nghĩa thống kê so với cả `CUTOFF = 7` ($p = 0.00014$) và `CUTOFF = 10` ($p = 0.0113$).
   - **`CUTOFF = 18 – 24` (Vùng tối ưu cân bằng toàn diện):** Tại `CUTOFF = 18`, mảng lớn $N = 10^6$ đạt cực tiểu `229.91 ms` (giảm **10.96%**), đa quy mô giảm **9.53%**, và ngay cả trường hợp xấu nhất mảng sắp xếp ngược giảm dần vẫn chạy nhanh hơn Baseline **7.84%**.
2. **Cập nhật hằng số mặc định & Xuất bản báo cáo:**
   - Cập nhật `DEFAULT_CUTOFF = 24` trong `src/MergeSort.java` kèm chú thích kết quả thực nghiệm.
   - Xuất báo cáo hoàn chỉnh sang 3 định dạng (`.md`, `.docx`, `.pdf`), kiểm tra hiển thị bảng biểu, công thức toán và 6 đồ thị 300 DPI, sau đó đóng gói trọn bộ sản phẩm nộp.

---

## Phiên 5 — Rà soát toàn bộ kết quả, cập nhật thông tin sinh viên và xuất bản lên GitHub (18/11/2026)

### [Người học]
> Hoàn thành đầy đủ các yêu cầu dự án để nộp bài, sử dụng cài đặt Mergesort chuẩn giáo trình, bổ sung thông tin sinh viên (`Nguyễn Bảo Đăng — MSV: 25020115 — Lớp: IT1-K70`) và đẩy toàn bộ sản phẩm lên GitHub (repo public `mergesort-cutoff-experiment`).

### [AI — Kiểm tra tính toàn vẹn & Xuất bản GitHub]
1. **Kiểm tra tái lập và tính nhất quán số liệu:**
   - Biên dịch sạch mã nguồn Java với `javac -Xlint:all` (`MergeSort.java`, `DatasetGenerator.java`, `BenchmarkRunner.java`, `CostModelAnalyzer.java`).
   - Đối chiếu kiểm tra toàn vẹn mã `SHA-256` của cả 14 tệp dữ liệu trong `datasets/` khớp 100% với `datasets/manifest.csv`.
   - Chạy kiểm chứng lại `CostModelAnalyzer` và đối chiếu khớp hoàn toàn với `results/cost_model_counts.csv`, đồng thời kiểm tra khớp toàn bộ bảng số liệu trong báo cáo với `results/summary_statistics.csv` và `results/multiscale_normalized_summary.csv`.
2. **Hoàn thiện báo cáo & Đóng gói GitHub:**
   - Cập nhật thông tin sinh viên (`Nguyễn Bảo Đăng — MSV: 25020115 — Lớp: IT1-K70`) vào `README.md` và `report/Bao_Cao_Thi_Nghiem_MergeSort_CUTOFF.md`, xuất lại đồng bộ hai định dạng `.pdf` và `.docx` (cũng như `ai_chat_log/Log_Chat_Voi_AI.pdf`).
   - Tạo `.gitignore` (loại bỏ tệp biên dịch tạm `bin/`, `*.class`, `.DS_Store`), khởi tạo kho lưu trữ Git và đẩy trọn bộ 4 nhóm sản phẩm nộp (báo cáo, mã nguồn & script, bộ dữ liệu thí nghiệm, log chat AI) lên GitHub công khai tại `SoWi1511/mergesort-cutoff-experiment`.
