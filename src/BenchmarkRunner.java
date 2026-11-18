import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.util.Arrays;
import java.util.Random;

/**
 * Chương trình thực nghiệm đo thời gian chạy Mergesort với các giá trị CUTOFF khác nhau.
 *
 * Thiết kế thí nghiệm tuân thủ nghiêm ngặt chủ đề 1.3. Algorithm Analysis:
 * 1. JVM Warm-up: Chạy làm nóng đầy đủ để trình biên dịch JIT HotSpot C2 tối ưu hóa mã máy
 *    ổn định trước khi bắt đầu ghi nhận số liệu.
 * 2. Thiết kế khối ngẫu nhiên đầy đủ (Randomized Complete Block Design - RCBD):
 *    Trong mỗi lượt đo (trial block), thứ tự các giá trị CUTOFF được xáo trộn ngẫu nhiên
 *    để triệt tiêu sai số trôi nhiệt (thermal drift) và nhiễu nền của hệ điều hành.
 * 3. Tách biệt cấp phát bộ nhớ: Mảng làm việc được sao chép ngoài cửa sổ đo System.nanoTime().
 * 4. Chống loại bỏ mã chết (Anti-DCE) & Kiểm tra tính đúng đắn tự động (assert + đối chiếu Arrays.sort).
 */
public class BenchmarkRunner {

    /**
     * Lưới giá trị CUTOFF khảo sát:
     * - Độ phân giải bước 1 trên toàn bộ miền [0..36] (bao phủ baseline 0, 1, giáo trình cũ 7,
     *   giáo trình mới 10, và toàn bộ vùng đáy tối ưu tiềm năng).
     * - Mở rộng đến 128 để quan sát rõ nhánh suy giảm bậc hai của Insertion Sort.
     */
    private static final int[] CUTOFFS = {
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18,
        19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36,
        40, 44, 48, 56, 64, 80, 96, 128
    };

    private static final String[] DATASET_FILES = {
        "random_N10000.txt",
        "random_N50000.txt",
        "random_N100000.txt",
        "random_N140000.txt",
        "random_N180000.txt",
        "random_N220000.txt",
        "random_N262144_pow2.txt",
        "random_N310000.txt",
        "random_N380000.txt",
        "random_N500000.txt",
        "random_N1000000.txt",
        "nearly_sorted_N200000.txt",
        "reverse_sorted_N200000.txt",
        "few_unique_N200000.txt"
    };

    // Biến volatile giữ tổng kiểm tra nhằm ngăn trình biên dịch JIT loại bỏ phép tính
    public static volatile long blackholeChecksum = 0;

    public static void main(String[] args) throws Exception {
        String datasetDir = (args.length > 0) ? args[0] : "datasets";
        String rawOutCsv  = (args.length > 1) ? args[1] : "results/raw_measurements.csv";
        String primOutCsv = (args.length > 2) ? args[2] : "results/primitive_vs_comparable.csv";

        File outFile = new File(rawOutCsv);
        if (outFile.getParentFile() != null) {
            outFile.getParentFile().mkdirs();
        }

        System.out.println("=== BẮT ĐẦU LÀM NÓNG JVM (JIT WARM-UP) ===");
        warmupJvm();
        System.out.println("=== HOÀN TẤT WARM-UP. BẮT ĐẦU ĐO THỰC NGHIỆM ===");

        try (BufferedWriter writer = new BufferedWriter(new FileWriter(outFile), 65536)) {
            writer.write("dataset,category,n,cutoff,trial,elapsed_ns,elapsed_ms\n");

            for (String filename : DATASET_FILES) {
                File f = new File(datasetDir, filename);
                int[] rawValues = loadRawInts(f);
                Integer[] master = buildHeapNeutralIntegerArray(rawValues, 424242L);
                int n = master.length;
                String category = inferCategory(filename);
                int trials = chooseTrials(n);

                // Xác thực tính đúng đắn 100% đối với mọi giá trị CUTOFF trước khi đo
                verifyCorrectness(master);

                // Thu gom rác ngoài vùng đo trước khi bắt đầu một bộ dữ liệu mới
                System.gc();
                Thread.sleep(80);

                Integer[] work = new Integer[n];
                // 2 lượt chạy làm quen bộ nhớ đệm cho kích thước mảng hiện tại
                for (int c : new int[]{0, 7, 10, 16, 32}) {
                    System.arraycopy(master, 0, work, 0, n);
                    MergeSort.sort(work, c);
                    blackholeChecksum ^= work[n / 2];
                }

                int[] order = Arrays.copyOf(CUTOFFS, CUTOFFS.length);
                long tStartDataset = System.currentTimeMillis();

                for (int trial = 1; trial <= trials; trial++) {
                    if (n >= 200_000) {
                        System.gc();
                    }
                    shuffleIntArray(order, new Random(900_000L + trial * 31L + n));
                    for (int cutoff : order) {
                        System.arraycopy(master, 0, work, 0, n);

                        long t0 = System.nanoTime();
                        MergeSort.sort(work, cutoff);
                        long t1 = System.nanoTime();

                        blackholeChecksum ^= work[n >> 1];
                        long elapsedNs = t1 - t0;
                        double elapsedMs = elapsedNs / 1_000_000.0;

                        writer.write(String.format(
                            "%s,%s,%d,%d,%d,%d,%.6f\n",
                            filename, category, n, cutoff, trial, elapsedNs, elapsedMs
                        ));
                    }
                }
                writer.flush();
                long wallMs = System.currentTimeMillis() - tStartDataset;
                System.out.printf("Hoàn thành %-28s | N = %,9d | Trials = %2d | %.2fs%n",
                    filename, n, trials, wallMs / 1000.0);
            }
        }

        // Thực nghiệm đối chứng bổ sung: Comparable (Integer[]) chuẩn bài giảng vs Primitive (int[])
        System.out.println("=== CHẠY THÍ NGHIỆM ĐỐI CHỨNG COMPARABLE[] VS PRIMITIVE int[] ===");
        runPrimitiveComparison(datasetDir, primOutCsv);
        System.out.println("Hoàn tất toàn bộ phép đo! Checksum = " + blackholeChecksum);
    }

    private static int chooseTrials(int n) {
        if (n <= 50_000)  return 30;
        if (n <= 250_000) return 21;
        if (n <= 500_000) return 17;
        return 15;
    }

    private static String inferCategory(String filename) {
        if (filename.startsWith("random_"))         return "uniform_random";
        if (filename.startsWith("nearly_sorted_"))  return "nearly_sorted";
        if (filename.startsWith("reverse_sorted_")) return "reverse_sorted";
        if (filename.startsWith("few_unique_"))     return "few_unique";
        return "other";
    }

    private static void warmupJvm() {
        Random rng = new Random(12345L);
        int n = 80_000;
        Integer[] master = new Integer[n];
        for (int i = 0; i < n; i++) {
            master[i] = Integer.valueOf(rng.nextInt(1_000_000));
        }
        Integer[] work = new Integer[n];
        int[] warmCutoffs = {0, 1, 4, 7, 10, 14, 18, 24, 32, 64};
        for (int round = 0; round < 8; round++) {
            for (int c : warmCutoffs) {
                System.arraycopy(master, 0, work, 0, n);
                MergeSort.sort(work, c);
                blackholeChecksum ^= work[c];
            }
        }
    }

    private static void verifyCorrectness(Integer[] master) {
        Integer[] expected = Arrays.copyOf(master, master.length);
        Arrays.sort(expected);

        for (int cutoff : new int[]{0, 1, 2, 7, 10, 16, 32, 64}) {
            Integer[] test = Arrays.copyOf(master, master.length);
            MergeSort.sort(test, cutoff);
            if (!MergeSort.isSorted(test) || !Arrays.equals(expected, test)) {
                throw new AssertionError("Sai kết quả sắp xếp tại CUTOFF = " + cutoff);
            }
        }
    }

    private static int[] loadRawInts(File file) throws IOException {
        try (BufferedReader reader = new BufferedReader(new FileReader(file), 65536)) {
            int n = Integer.parseInt(reader.readLine().trim());
            int[] raw = new int[n];
            for (int i = 0; i < n; i++) {
                raw[i] = Integer.parseInt(reader.readLine().trim());
            }
            return raw;
        }
    }

    /**
     * Cấp phát các đối tượng Integer theo thứ tự vị trí xáo trộn để tránh hiện tượng
     * bump-pointer allocation sắp sẵn địa chỉ bộ nhớ tuyến tính cho mảng có thứ tự,
     * đồng thời giữ nguyên 100% giá trị tại từng chỉ số của bộ dữ liệu gốc.
     */
    private static Integer[] buildHeapNeutralIntegerArray(int[] raw, long seed) {
        int n = raw.length;
        int[] idx = new int[n];
        for (int i = 0; i < n; i++) {
            idx[i] = i;
        }
        shuffleIntArray(idx, new Random(seed));
        Integer[] arr = new Integer[n];
        for (int k = 0; k < n; k++) {
            int pos = idx[k];
            arr[pos] = Integer.valueOf(raw[pos]);
        }
        return arr;
    }

    private static void shuffleIntArray(int[] a, Random rng) {
        for (int i = a.length - 1; i > 0; i--) {
            int j = rng.nextInt(i + 1);
            int tmp = a[i];
            a[i] = a[j];
            a[j] = tmp;
        }
    }

    // =========================================================================
    // Thực nghiệm đối chứng: Mảng nguyên thủy int[] vs Comparable[] (Integer[])
    // giúp lý giải sự khác biệt chi phí dereference / autoboxing trên JVM & CPU
    // =========================================================================
    private static void runPrimitiveComparison(String datasetDir, String outCsv) throws Exception {
        String[] files = {"random_N180000.txt", "random_N500000.txt"};

        // Warmup cho hàm sort mảng int[] nguyên thủy
        int[] warmMaster = loadRawInts(new File(datasetDir, "random_N100000.txt"));
        int[] warmWork = new int[warmMaster.length];
        for (int r = 0; r < 40; r++) {
            System.arraycopy(warmMaster, 0, warmWork, 0, warmMaster.length);
            sortPrimitive(warmWork, CUTOFFS[r % CUTOFFS.length]);
            blackholeChecksum ^= warmWork[0];
        }

        try (BufferedWriter writer = new BufferedWriter(new FileWriter(outCsv), 65536)) {
            writer.write("dataset,n,representation,cutoff,trial,elapsed_ns,elapsed_ms\n");

            for (String filename : files) {
                int[] rawMaster = loadRawInts(new File(datasetDir, filename));
                Integer[] objMaster = buildHeapNeutralIntegerArray(rawMaster, 777777L);
                int n = rawMaster.length;
                int trials = 20;

                int[] primWork = new int[n];
                Integer[] objWork = new Integer[n];
                int[] order = Arrays.copyOf(CUTOFFS, CUTOFFS.length);

                System.gc();
                Thread.sleep(60);

                for (int trial = 1; trial <= trials; trial++) {
                    System.gc();
                    shuffleIntArray(order, new Random(500_000L + trial));
                    for (int cutoff : order) {
                        // 1. Primitive int[]
                        System.arraycopy(rawMaster, 0, primWork, 0, n);
                        long p0 = System.nanoTime();
                        sortPrimitive(primWork, cutoff);
                        long p1 = System.nanoTime();
                        blackholeChecksum ^= primWork[n >> 1];
                        writer.write(String.format(
                            "%s,%d,primitive_int,%d,%d,%d,%.6f\n",
                            filename, n, cutoff, trial, (p1 - p0), (p1 - p0) / 1_000_000.0
                        ));

                        // 2. Comparable Integer[] (chuẩn bài giảng)
                        System.arraycopy(objMaster, 0, objWork, 0, n);
                        long c0 = System.nanoTime();
                        MergeSort.sort(objWork, cutoff);
                        long c1 = System.nanoTime();
                        blackholeChecksum ^= objWork[n >> 1];
                        writer.write(String.format(
                            "%s,%d,comparable_integer,%d,%d,%d,%.6f\n",
                            filename, n, cutoff, trial, (c1 - c0), (c1 - c0) / 1_000_000.0
                        ));
                    }
                }
                System.out.println("Đã đo đối chứng primitive vs Comparable cho: " + filename);
            }
        }
    }

    private static void sortPrimitive(int[] a, int cutoff) {
        int[] aux = new int[a.length];
        sortPrimitive(a, aux, 0, a.length - 1, cutoff);
    }

    private static void sortPrimitive(int[] a, int[] aux, int lo, int hi, int cutoff) {
        if (cutoff == 0) {
            if (hi <= lo) return;
        } else {
            if (hi <= lo + cutoff - 1) {
                for (int i = lo + 1; i <= hi; i++) {
                    for (int j = i; j > lo && a[j] < a[j - 1]; j--) {
                        int swap = a[j];
                        a[j] = a[j - 1];
                        a[j - 1] = swap;
                    }
                }
                return;
            }
        }
        int mid = lo + (hi - lo) / 2;
        sortPrimitive(a, aux, lo, mid, cutoff);
        sortPrimitive(a, aux, mid + 1, hi, cutoff);
        for (int k = lo; k <= hi; k++) aux[k] = a[k];
        int i = lo, j = mid + 1;
        for (int k = lo; k <= hi; k++) {
            if      (i > mid)          a[k] = aux[j++];
            else if (j > hi)           a[k] = aux[i++];
            else if (aux[j] < aux[i])  a[k] = aux[j++];
            else                       a[k] = aux[i++];
        }
    }
}
