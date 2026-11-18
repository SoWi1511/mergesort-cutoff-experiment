/**
 * Cài đặt Top-down Mergesort kết hợp cải tiến CUTOFF sang Insertion Sort
 * đối với mảng con kích thước nhỏ, dựng trực tiếp từ nội dung bài giảng
 * (giáo trình Algorithms, 4th Edition - Robert Sedgewick & Kevin Wayne).
 *
 * Quy ước CUTOFF:
 * - cutoff == 0: Mergesort thuần túy chuẩn bài giảng (điều kiện dừng: hi <= lo),
 *                không gọi Insertion Sort.
 * - cutoff >= 1: Khi độ dài mảng con (hi - lo + 1) <= cutoff
 *                (tương đương hi <= lo + cutoff - 1), chuyển sang sắp xếp
 *                đoạn a[lo..hi] bằng Insertion Sort.
 */
@SuppressWarnings({"rawtypes", "unchecked"})
public class MergeSort {

    /**
     * Giá trị CUTOFF mặc định được xác lập từ kết quả thực nghiệm đa quy mô
     * trên cấu hình Apple M4 (10-core, L1d 128KB, L2 16MB) - Oracle JDK 25 LTS:
     * đạt cực tiểu thời gian chuẩn hóa tại CUTOFF = 24 (vùng tối ưu [18..24]).
     */
    public static final int DEFAULT_CUTOFF = 24;

    // Không cho phép khởi tạo đối tượng từ lớp tiện ích
    private MergeSort() {
    }

    /**
     * Sắp xếp mảng a[] theo thứ tự không giảm với giá trị CUTOFF mặc định.
     *
     * @param a mảng các phần tử Comparable cần sắp xếp
     */
    public static void sort(Comparable[] a) {
        sort(a, DEFAULT_CUTOFF);
    }

    /**
     * Sắp xếp mảng a[] theo thứ tự không giảm với ngưỡng CUTOFF chỉ định.
     * Mảng phụ aux[] được cấp phát đúng 1 lần duy nhất trước khi gọi đệ quy.
     *
     * @param a      mảng các phần tử Comparable cần sắp xếp
     * @param cutoff ngưỡng độ dài mảng con tối đa áp dụng Insertion Sort
     */
    public static void sort(Comparable[] a, int cutoff) {
        if (a == null || a.length <= 1) {
            return;
        }
        if (cutoff < 0) {
            throw new IllegalArgumentException("Giá trị CUTOFF phải >= 0: " + cutoff);
        }
        Comparable[] aux = new Comparable[a.length];
        sort(a, aux, 0, a.length - 1, cutoff);
        assert isSorted(a);
    }

    /**
     * Hàm đệ quy Top-down Mergesort trên đoạn a[lo..hi].
     */
    private static void sort(Comparable[] a, Comparable[] aux, int lo, int hi, int cutoff) {
        if (cutoff == 0) {
            if (hi <= lo) {
                return;
            }
        } else {
            if (hi <= lo + cutoff - 1) {
                insertionSort(a, lo, hi);
                return;
            }
        }

        int mid = lo + (hi - lo) / 2;
        sort(a, aux, lo, mid, cutoff);
        sort(a, aux, mid + 1, hi, cutoff);
        merge(a, aux, lo, mid, hi);
    }

    /**
     * Trộn hai nửa đã sắp xếp a[lo..mid] và a[mid+1..hi] thành đoạn đã sắp xếp a[lo..hi]
     * thông qua mảng phụ aux[] (Abstract in-place merge theo bài giảng).
     */
    private static void merge(Comparable[] a, Comparable[] aux, int lo, int mid, int hi) {
        assert isSorted(a, lo, mid);
        assert isSorted(a, mid + 1, hi);

        // Sao chép đoạn a[lo..hi] sang mảng phụ aux[]
        for (int k = lo; k <= hi; k++) {
            aux[k] = a[k];
        }

        // Trộn ngược trở lại mảng a[]
        int i = lo;
        int j = mid + 1;
        for (int k = lo; k <= hi; k++) {
            if      (i > mid)              a[k] = aux[j++];
            else if (j > hi)               a[k] = aux[i++];
            else if (less(aux[j], aux[i])) a[k] = aux[j++];
            else                           a[k] = aux[i++];
        }

        assert isSorted(a, lo, hi);
    }

    /**
     * Insertion Sort sắp xếp trực tiếp trên đoạn con a[lo..hi] (theo bài giảng 2.1 Elementary Sorts).
     */
    private static void insertionSort(Comparable[] a, int lo, int hi) {
        for (int i = lo + 1; i <= hi; i++) {
            for (int j = i; j > lo && less(a[j], a[j - 1]); j--) {
                exch(a, j, j - 1);
            }
        }
    }

    /**
     * So sánh v < w thông qua giao diện Comparable.
     */
    private static boolean less(Comparable v, Comparable w) {
        return v.compareTo(w) < 0;
    }

    /**
     * Hoán đổi hai phần tử a[i] và a[j].
     */
    private static void exch(Object[] a, int i, int j) {
        Object swap = a[i];
        a[i] = a[j];
        a[j] = swap;
    }

    /**
     * Kiểm tra đoạn a[lo..hi] đã được sắp xếp không giảm hay chưa.
     */
    private static boolean isSorted(Comparable[] a, int lo, int hi) {
        for (int i = lo + 1; i <= hi; i++) {
            if (less(a[i], a[i - 1])) {
                return false;
            }
        }
        return true;
    }

    /**
     * Kiểm tra toàn bộ mảng a[] đã được sắp xếp không giảm hay chưa.
     */
    public static boolean isSorted(Comparable[] a) {
        if (a == null || a.length <= 1) {
            return true;
        }
        return isSorted(a, 0, a.length - 1);
    }
}
