import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Random;

/**
 * Chương trình sinh bộ dữ liệu thí nghiệm chuẩn hóa với hạt giống ngẫu nhiên (seed) cố định
 * nhằm đảm bảo tính tái lập hoàn toàn (100% reproducibility) theo phương pháp thực nghiệm
 * của chủ đề 1.3. Algorithm Analysis.
 *
 * Bộ dữ liệu gồm 2 nhóm:
 * 1. Nhóm đa quy mô ngẫu nhiên phân phối đều (Uniform Random):
 *    - N = 10,000; 50,000; 100,000; 140,000; 180,000; 220,000; 262,144 (2^18);
 *      310,000; 380,000; 500,000; 1,000,000.
 *    - Các giá trị N trong đoạn [100k..500k] được chọn sao cho phần lẻ của log2(N)
 *      phân bố đều trên [0, 1), giúp kích thước mảng con ở tầng lá bao phủ đầy đủ mọi
 *      số nguyên liên tiếp (4..19) và tránh sai lệch lượng tử hóa cây chia đôi.
 * 2. Nhóm kiểm chứng theo đặc trưng phân phối đầu vào (N = 200,000):
 *    - nearly_sorted: Mảng gần sắp xếp (2% phép tráo ngẫu nhiên).
 *    - reverse_sorted: Mảng giảm dần ngặt (trường hợp xấu nhất của Insertion Sort).
 *    - few_unique: Mảng nhiều khóa trùng lặp (chỉ gồm 50 giá trị phân biệt).
 */
public class DatasetGenerator {

    private record Spec(String filename, String category, int n, long seed, String description) {}

    private static final Spec[] SPECS = {
        new Spec("random_N10000.txt",          "uniform_random",  10_000,    2026101L, "Ngau nhien deu N=10,000 (quy mo nho)"),
        new Spec("random_N50000.txt",          "uniform_random",  50_000,    2026102L, "Ngau nhien deu N=50,000 (quy mo vua nho)"),
        new Spec("random_N100000.txt",         "uniform_random",  100_000,   2026103L, "Ngau nhien deu N=100,000 (la: 6/7, 12/13)"),
        new Spec("random_N140000.txt",         "uniform_random",  140_000,   2026104L, "Ngau nhien deu N=140,000 (la: 4/5, 8/9, 17/18)"),
        new Spec("random_N180000.txt",         "uniform_random",  180_000,   2026105L, "Ngau nhien deu N=180,000 (la: 5/6, 10/11)"),
        new Spec("random_N220000.txt",         "uniform_random",  220_000,   2026106L, "Ngau nhien deu N=220,000 (la: 6/7, 13/14)"),
        new Spec("random_N262144_pow2.txt",    "uniform_random",  262_144,   2026107L, "Ngau nhien deu N=262,144=2^18 (la luy thua 2: 4, 8, 16, 32)"),
        new Spec("random_N310000.txt",         "uniform_random",  310_000,   2026108L, "Ngau nhien deu N=310,000 (la: 4/5, 9/10, 18/19)"),
        new Spec("random_N380000.txt",         "uniform_random",  380_000,   2026109L, "Ngau nhien deu N=380,000 (la: 5/6, 11/12)"),
        new Spec("random_N500000.txt",         "uniform_random",  500_000,   2026110L, "Ngau nhien deu N=500,000 (la: 7/8, 15/16)"),
        new Spec("random_N1000000.txt",        "uniform_random",  1_000_000, 2026111L, "Ngau nhien deu N=1,000,000 (quy mo lon)"),
        new Spec("nearly_sorted_N200000.txt",  "nearly_sorted",   200_000,   2026201L, "Gan sap xep N=200,000 (2% hoan doi ngau nhien)"),
        new Spec("reverse_sorted_N200000.txt", "reverse_sorted",  200_000,   2026202L, "Sap xep nguoc giam dan N=200,000 (worst-case Insertion Sort)"),
        new Spec("few_unique_N200000.txt",     "few_unique",      200_000,   2026203L, "Nhieu trung lap N=200,000 (50 gia tri phan biet)")
    };

    public static void main(String[] args) throws Exception {
        String outDirPath = (args.length > 0) ? args[0] : "datasets";
        File outDir = new File(outDirPath);
        if (!outDir.exists() && !outDir.mkdirs()) {
            throw new IOException("Không thể tạo thư mục: " + outDirPath);
        }

        File manifestFile = new File(outDir, "manifest.csv");
        try (BufferedWriter manifest = new BufferedWriter(new FileWriter(manifestFile))) {
            manifest.write("filename,category,n,seed,sha256,description\n");

            for (Spec spec : SPECS) {
                int[] data = generateArray(spec);
                File target = new File(outDir, spec.filename());
                writeDataset(target, data);
                String sha256 = computeSha256(target);

                manifest.write(String.format(
                    "%s,%s,%d,%d,%s,\"%s\"\n",
                    spec.filename(), spec.category(), spec.n(), spec.seed(), sha256, spec.description()
                ));
                System.out.printf("Đã tạo %-28s | N = %,9d | SHA-256 = %s...%n",
                    spec.filename(), spec.n(), sha256.substring(0, 12));
            }
        }
        System.out.println("Hoàn tất sinh bộ dữ liệu thí nghiệm tại: " + outDir.getAbsolutePath());
    }

    private static int[] generateArray(Spec spec) {
        int n = spec.n();
        int[] a = new int[n];
        Random rng = new Random(spec.seed());

        switch (spec.category()) {
            case "uniform_random" -> {
                for (int i = 0; i < n; i++) {
                    a[i] = rng.nextInt(1_000_000);
                }
            }
            case "nearly_sorted" -> {
                for (int i = 0; i < n; i++) {
                    a[i] = i;
                }
                int swaps = Math.max(1, (int) (0.02 * n));
                for (int s = 0; s < swaps; s++) {
                    int i = rng.nextInt(n);
                    int j = rng.nextInt(n);
                    int tmp = a[i];
                    a[i] = a[j];
                    a[j] = tmp;
                }
            }
            case "reverse_sorted" -> {
                for (int i = 0; i < n; i++) {
                    a[i] = n - i;
                }
            }
            case "few_unique" -> {
                for (int i = 0; i < n; i++) {
                    a[i] = rng.nextInt(50);
                }
            }
            default -> throw new IllegalArgumentException("Loại dữ liệu không xác định: " + spec.category());
        }
        return a;
    }

    private static void writeDataset(File file, int[] data) throws IOException {
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(file), 65536)) {
            writer.write(Integer.toString(data.length));
            writer.newLine();
            for (int v : data) {
                writer.write(Integer.toString(v));
                writer.newLine();
            }
        }
    }

    private static String computeSha256(File file) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] bytes = Files.readAllBytes(file.toPath());
        return HexFormat.of().formatHex(md.digest(bytes));
    }
}
