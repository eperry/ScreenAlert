"""Tune background-subtraction parameters against diagnostic D_scan images.

Usage:
    python tools/tune_bg_params.py --diagnostics <path-to-diagnostics>

The script searches for image triplets containing '_prev' and '_curr' (D_scan
pairs) in the diagnostics folder, trains an OpenCV MOG2 detector on the
previous frame, then evaluates whether the detector flags the current frame
as an alert. It performs a grid search over varThreshold (variance) and
min foreground fraction to find a combination that does NOT alert on the
provided false-positive examples.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Tuple

from PIL import Image
import numpy as np

from screenalert_core.core.change_detectors import MOG2Detector


def find_dscan_pairs(root: str) -> Dict[str, Dict[str, str]]:
    pairs: Dict[str, Dict[str, str]] = {}
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if not fn.lower().endswith('.png'):
                continue
            lower = fn.lower()
            if '_d_scan' in lower or '_d-scan' in lower or 'd_scan' in lower:
                base = fn
                # Determine suffix type
                if '_prev' in lower:
                    key = fn[: lower.rfind('_prev')]
                    pairs.setdefault(key, {})['prev'] = os.path.join(dirpath, fn)
                elif '_curr' in lower:
                    key = fn[: lower.rfind('_curr')]
                    pairs.setdefault(key, {})['curr'] = os.path.join(dirpath, fn)
                elif '_diff' in lower:
                    key = fn[: lower.rfind('_diff')]
                    pairs.setdefault(key, {})['diff'] = os.path.join(dirpath, fn)
                # also match variants like '_alert_edges_prev'
                elif '_alert_edges_prev' in lower:
                    key = fn[: lower.rfind('_alert_edges_prev')]
                    pairs.setdefault(key, {})['prev'] = os.path.join(dirpath, fn)
                elif '_alert_edges_curr' in lower:
                    key = fn[: lower.rfind('_alert_edges_curr')]
                    pairs.setdefault(key, {})['curr'] = os.path.join(dirpath, fn)
                elif '_alert_edges_diff' in lower:
                    key = fn[: lower.rfind('_alert_edges_diff')]
                    pairs.setdefault(key, {})['diff'] = os.path.join(dirpath, fn)
    # Filter to only those with both prev and curr
    valid = {k: v for k, v in pairs.items() if 'prev' in v and 'curr' in v}
    return valid


def load_gray(path: str) -> np.ndarray:
    img = Image.open(path).convert('L')
    return np.array(img, dtype=np.uint8)


def evaluate_params(pairs: Dict[str, Dict[str, str]], var_t: float, min_fg: float,
                    warmup_replays: int = 10) -> Tuple[bool, Dict[str, bool]]:
    """Return (all_ok, details)

    all_ok is True if NONE of the pairs produce an alert with these params.
    details maps key -> detected_bool
    """
    details: Dict[str, bool] = {}
    for key, files in pairs.items():
        prev = load_gray(files['prev'])
        curr = load_gray(files['curr'])

        det = MOG2Detector(var_threshold=var_t, min_fg_fraction=min_fg,
                            warmup_frames=5, history=200, learning_rate=0.5)

        # Feed the previous frame repeatedly to build the background model
        try:
            for _ in range(max(1, warmup_replays)):
                # direct apply to the underlying subtractor to quickly warm
                det._subtractor.apply(prev, learningRate=0.5)
        except Exception:
            # fallback: call detect with prev to warm
            for _ in range(max(1, warmup_replays)):
                det.detect(prev, prev)

        # Now evaluate the current frame
        try:
            changed = det.detect(prev, Image.fromarray(curr))
        except Exception:
            # If detect expects PIL.Image for curr, convert
            changed = det.detect(Image.fromarray(prev), Image.fromarray(curr))

        details[key] = bool(changed)

    all_ok = not any(details.values())
    return all_ok, details


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--diagnostics', '-d', required=False,
                   default=os.path.join(os.getenv('APPDATA', ''), 'ScreenAlert', 'captures', 'diagnostics'),
                   help='Path to diagnostics folder')
    args = p.parse_args()

    diag = args.diagnostics
    if not os.path.isdir(diag):
        print('Diagnostics folder not found:', diag)
        sys.exit(2)

    pairs = find_dscan_pairs(diag)
    if not pairs:
        print('No D_scan prev/curr pairs found in', diag)
        sys.exit(1)

    print(f'Found {len(pairs)} D_scan pairs to evaluate')

    # Parameter grids (coarse -> finer)
    var_vals = [4.0, 8.0, 12.0, 16.0, 20.0, 24.0, 32.0, 48.0, 64.0, 96.0, 128.0]
    min_fg_vals = [0.0005, 0.001, 0.002, 0.003, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2]

    for var_t in var_vals:
        for min_fg in min_fg_vals:
            ok, details = evaluate_params(pairs, var_t, min_fg, warmup_replays=8)
            print(f'var={var_t:>6}  min_fg={min_fg:<7}  -> all_ok={ok}  details={details}')
            if ok:
                print('\nFOUND parameters that avoid alerts:')
                print('  var_threshold =', var_t)
                print('  min_fg_fraction =', min_fg)
                return

    print('\nNo parameter combination from the grid avoided alerts for all samples.')


if __name__ == '__main__':
    main()
