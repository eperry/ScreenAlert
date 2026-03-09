"""
Analyze D-scan alert region diagnostic pairs to find the best metric
for separating true content changes from false nebula-shift alerts.

Usage:  PYTHONPATH=. python tools/analyze_dscan_pairs.py
"""

import glob
import os
import re
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim


DIAG_DIR = r"C:\Users\Ed\AppData\Roaming\ScreenAlert\captures\diagnostics"
PATTERN = "*D_scan_alert_region_prev.png"

# Ground-truth labels from manual review
# TRUE  = real content change  (text appeared/disappeared)
# FALSE = nebula background shift only
# None  = unknown, to be classified by inspecting text similarity
LABELS = {
    "130134": "TRUE",    # No Scan Results -> Patronus appeared
    "130157": "FALSE",   # same Patronus result, nebula shifted
    "130528": "TRUE",    # Patronus -> No Scan Results
    "130736": None,
    "130916": None,
    "133911": None,
    "134023": None,
    "134627": None,
}


def canny_edges(gray, binarize=False):
    """Replicate EdgeDetector._canny: bilateral -> optional binarize -> Gaussian -> Canny 40/120."""
    filtered = cv2.bilateralFilter(gray, 9, 75, 75)
    if binarize:
        filtered = cv2.adaptiveThreshold(
            filtered, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11, C=2,
        )
    blurred = cv2.GaussianBlur(filtered, (3, 3), 0)
    return cv2.Canny(blurred, threshold1=40, threshold2=120)


def edge_diff_pct(prev_gray, curr_gray, binarize=False):
    e1 = canny_edges(prev_gray, binarize=binarize)
    e2 = canny_edges(curr_gray, binarize=binarize)
    changed = int(np.count_nonzero(e1 != e2))
    return changed / max(1, prev_gray.size) * 100


def ssim_score(prev_gray, curr_gray):
    return ssim(prev_gray, curr_gray)


def mog2_fg_pct(prev_bgr, curr_bgr, warmup=10):
    sub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16.0)
    for _ in range(warmup):
        sub.apply(prev_bgr)
    mask = sub.apply(curr_bgr)
    fg = int(np.count_nonzero(mask > 0))
    return fg / max(1, mask.size) * 100


def pixel_diff_pct(prev_gray, curr_gray):
    """Absolute pixel difference, returned as mean intensity difference %."""
    diff = cv2.absdiff(prev_gray, curr_gray).astype(np.float64)
    return diff.mean() / 255.0 * 100


def text_region_analysis(prev_gray, curr_gray, header_frac=0.25):
    """Split into header (top 25%) and content (bottom 75%), return pixel diff % for each."""
    h = prev_gray.shape[0]
    split = int(h * header_frac)
    header_diff = pixel_diff_pct(prev_gray[:split], curr_gray[:split])
    content_diff = pixel_diff_pct(prev_gray[split:], curr_gray[split:])
    return header_diff, content_diff


def binarized_pixel_diff(prev_gray, curr_gray):
    """Adaptive-threshold both frames to isolate text, then compute diff %."""
    b1 = cv2.adaptiveThreshold(prev_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, blockSize=11, C=2)
    b2 = cv2.adaptiveThreshold(curr_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, blockSize=11, C=2)
    changed = int(np.count_nonzero(b1 != b2))
    return changed / max(1, prev_gray.size) * 100


def classify_by_text(prev_gray, curr_gray):
    """Heuristic: if binarized pixel diff is very low, content is the same -> FALSE alert."""
    bdiff = binarized_pixel_diff(prev_gray, curr_gray)
    return "FALSE" if bdiff < 5.0 else "TRUE"


def main():
    prev_files = sorted(glob.glob(os.path.join(DIAG_DIR, PATTERN)))
    if not prev_files:
        print(f"No files found matching {PATTERN} in {DIAG_DIR}")
        return

    results = []
    for prev_path in prev_files:
        curr_path = prev_path.replace("_prev.png", "_curr.png")
        if not os.path.exists(curr_path):
            continue

        # Extract timestamp key (e.g. "130134")
        basename = os.path.basename(prev_path)
        m = re.search(r"_(\d{6})_", basename)
        if not m:
            continue
        ts = m.group(1)

        prev_bgr = cv2.imread(prev_path)
        curr_bgr = cv2.imread(curr_path)
        prev_gray = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_bgr, cv2.COLOR_BGR2GRAY)

        s = ssim_score(prev_gray, curr_gray)
        edge = edge_diff_pct(prev_gray, curr_gray, binarize=False)
        edge_bin = edge_diff_pct(prev_gray, curr_gray, binarize=True)
        mog2 = mog2_fg_pct(prev_bgr, curr_bgr)
        header_d, content_d = text_region_analysis(prev_gray, curr_gray)
        bin_px = binarized_pixel_diff(prev_gray, curr_gray)

        label = LABELS.get(ts)
        if label is None:
            label = classify_by_text(prev_gray, curr_gray)
            label_src = "auto"
        else:
            label_src = "manual"

        results.append({
            "ts": ts,
            "label": label,
            "label_src": label_src,
            "ssim": s,
            "edge_diff": edge,
            "edge_bin_diff": edge_bin,
            "mog2_fg": mog2,
            "header_diff": header_d,
            "content_diff": content_d,
            "bin_px_diff": bin_px,
        })

    # ── Print individual results ──────────────────────────────────────
    hdr = (f"{'Time':>6}  {'Label':>5} {'Src':>4}  "
           f"{'SSIM':>6}  {'Edge%':>6}  {'EdgBin%':>7}  {'MOG2%':>6}  "
           f"{'Hdr%':>6}  {'Cont%':>6}  {'BinPx%':>6}")
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        print(f"{r['ts']:>6}  {r['label']:>5} {r['label_src']:>4}  "
              f"{r['ssim']:6.4f}  {r['edge_diff']:6.3f}  {r['edge_bin_diff']:7.3f}  "
              f"{r['mog2_fg']:6.3f}  "
              f"{r['header_diff']:6.3f}  {r['content_diff']:6.3f}  {r['bin_px_diff']:6.3f}")

    # ── Summary by class ──────────────────────────────────────────────
    true_rs = [r for r in results if r["label"] == "TRUE"]
    false_rs = [r for r in results if r["label"] == "FALSE"]

    def avg(lst, key):
        return sum(r[key] for r in lst) / max(1, len(lst))

    metrics = ["ssim", "edge_diff", "edge_bin_diff", "mog2_fg",
               "header_diff", "content_diff", "bin_px_diff"]

    print("\n\n=== SUMMARY: TRUE changes vs FALSE alerts ===\n")
    print(f"  TRUE  count: {len(true_rs)}")
    print(f"  FALSE count: {len(false_rs)}")

    print(f"\n{'Metric':>14}  {'TRUE avg':>10}  {'FALSE avg':>10}  {'Gap':>10}  {'Separation':>10}")
    print("-" * 62)
    for m in metrics:
        ta = avg(true_rs, m)
        fa = avg(false_rs, m)
        gap = abs(ta - fa)
        # Separation ratio: gap / max(stdev_true, stdev_false, 0.001)
        t_vals = [r[m] for r in true_rs]
        f_vals = [r[m] for r in false_rs]
        pooled_std = max(
            np.std(t_vals) if len(t_vals) > 1 else 0.001,
            np.std(f_vals) if len(f_vals) > 1 else 0.001,
            0.001
        )
        sep = gap / pooled_std
        print(f"{m:>14}  {ta:10.4f}  {fa:10.4f}  {gap:10.4f}  {sep:10.2f}")

    # ── Range analysis ────────────────────────────────────────────────
    print("\n\n=== RANGE ANALYSIS (can a threshold perfectly separate?) ===\n")
    for m in metrics:
        t_vals = [r[m] for r in true_rs]
        f_vals = [r[m] for r in false_rs]
        t_min, t_max = min(t_vals), max(t_vals)
        f_min, f_max = min(f_vals), max(f_vals)
        # For SSIM, TRUE changes have LOWER values; for diffs, TRUE has HIGHER
        if m == "ssim":
            separable = t_max < f_min
            direction = "TRUE < threshold < FALSE"
        else:
            separable = t_min > f_max
            direction = "FALSE < threshold < TRUE"
        print(f"  {m:>14}:  TRUE=[{t_min:.4f}, {t_max:.4f}]  "
              f"FALSE=[{f_min:.4f}, {f_max:.4f}]  "
              f"{'SEPARABLE' if separable else 'OVERLAP'}  ({direction})")


if __name__ == "__main__":
    main()
