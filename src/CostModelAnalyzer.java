import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;

/**
 * Bộ phân tích Mô hình Chi phí (Cost Model Analyzer) dựa trên chủ đề 1.3. Algorithm Analysis.
 * Đếm chính xác số lượng phép toán cơ bản của cài đặt Top-down Mergesort + CUTOFF:
 * - compares:       Tổng số phép so sánh khóa less(v, w)
 * - mergeCompares:  Số phép so sánh trong bước trộn merge()
 * - insertCompares: Số phép so sánh trong Insertion Sort
 * - arrayWrites:    Tổng số lần ghi vào mảng (sao chép sang aux, trộn về a, và hoán đổi exch)
 * - recursiveCalls: Tổng số lời gọi hàm đệ quy sort(a, aux, lo, hi)
 * - mergeCalls:     Tổng số lần thực hiện phép trộn merge()
 * - insertionCalls: Tổng số mảnh mảng con ở tầng lá được xử lý bởi Insertion Sort
 *
 * Tách biệt hoàn toàn khỏi MergeSort.java để không gây nhiễu thời gian chạy khi benchmark.
 */
@SuppressWarnings({"rawtypes", "unchecked"})
public class CostModelAnalyzer {

    private static long mergeCompares;
    private static long insertCompares;
    private static long arrayWrites;
    private static long recursiveCalls;
    private static long mergeCalls;
    private static long insertionCalls;

    private static final int[] CUTOFFS = {
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
        17, 18, 19, 20, 22, 24, 26, 28, 30, 32, 36, 40, 48, 56, 64, 80, 96, 128
    };

    public static void main(String[] args) throws IOException {
        String datasetDir = (args.length > 0) ? args[0] : "datasets";
        String outCsv = (args.length > 1) ? args[1] : "results/cost_model_counts.csv";

        File outFile = new File(outCsv);
        if (outFile.getParentFile() != null) {
            outFile.getParentFile().mkdirs();
        }

        // Phân tích trên cả mảng N=1,000,000, N=262,144 (2^18) và đa quy mô
        String[] targetFiles = {
            "random_N100000.txt",
            "random_N180000.txt",
            "random_N262144_pow2.txt",
            "random_N500000.txt",
            "random_N1000000.txt",
            "nearly_sorted_N200000.txt",
            "reverse_sorted_N200000.txt"
        };

        try (BufferedWriter writer = new BufferedWriter(new FileWriter(outFile))) {
            writer.write("dataset,n,cutoff,total_compares,merge_compares,insert_compares,array_writes,recursive_calls,merge_calls,insertion_calls\n");

            for (String filename : targetFiles) {
                Integer[] master = loadDataset(new File(datasetDir, filename));
                int n = master.length;
                Integer[] work = new Integer[n];

                for (int cutoff : CUTOFFS) {
                    System.arraycopy(master, 0, work, 0, n);
                    resetCounters();

                    Comparable[] aux = new Comparable[n];
                    sortCounted(work, aux, 0, n - 1, cutoff);

                    long totalCompares = mergeCompares + insertCompares;
                    writer.write(String.format(
                        "%s,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
                        filename, n, cutoff,
                        totalCompares, mergeCompares, insertCompares,
                        arrayWrites, recursiveCalls, mergeCalls, insertionCalls
                    ));
                }
                System.out.println("Đã thống kê mô hình chi phí cho: " + filename);
            }
        }
    }

    private static void resetCounters() {
        mergeCompares = 0;
        insertCompares = 0;
        arrayWrites = 0;
        recursiveCalls = 0;
        mergeCalls = 0;
        insertionCalls = 0;
    }

    private static void sortCounted(Comparable[] a, Comparable[] aux, int lo, int hi, int cutoff) {
        recursiveCalls++;
        if (cutoff == 0) {
            if (hi <= lo) {
                return;
            }
        } else {
            if (hi <= lo + cutoff - 1) {
                insertionCalls++;
                insertionSortCounted(a, lo, hi);
                return;
            }
        }

        int mid = lo + (hi - lo) / 2;
        sortCounted(a, aux, lo, mid, cutoff);
        sortCounted(a, aux, mid + 1, hi, cutoff);
        mergeCalls++;
        mergeCounted(a, aux, lo, mid, hi);
    }

    private static void mergeCounted(Comparable[] a, Comparable[] aux, int lo, int mid, int hi) {
        for (int k = lo; k <= hi; k++) {
            aux[k] = a[k];
            arrayWrites++;
        }
        int i = lo;
        int j = mid + 1;
        for (int k = lo; k <= hi; k++) {
            if (i > mid) {
                a[k] = aux[j++];
            } else if (j > hi) {
                a[k] = aux[i++];
            } else {
                mergeCompares++;
                if (aux[j].compareTo(aux[i]) < 0) {
                    a[k] = aux[j++];
                } else {
                    a[k] = aux[i++];
                }
            }
            arrayWrites++;
        }
    }

    private static void insertionSortCounted(Comparable[] a, int lo, int hi) {
        for (int i = lo + 1; i <= hi; i++) {
            for (int j = i; j > lo; j--) {
                insertCompares++;
                if (a[j].compareTo(a[j - 1]) < 0) {
                    Comparable swap = a[j];
                    a[j] = a[j - 1];
                    a[j - 1] = swap;
                    arrayWrites += 2;
                } else {
                    break;
                }
            }
        }
    }

    static Integer[] loadDataset(File file) throws IOException {
        try (BufferedReader reader = new BufferedReader(new FileReader(file), 65536)) {
            int n = Integer.parseInt(reader.readLine().trim());
            Integer[] data = new Integer[n];
            for (int i = 0; i < n; i++) {
                data[i] = Integer.valueOf(Integer.parseInt(reader.readLine().trim()));
            }
            return data;
        }
    }
}
