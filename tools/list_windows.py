import win32gui
import win32process
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--match', required=True)
args = parser.parse_args()
needle = args.match.lower()

matches = []

def enum(hwnd, lparam):
    try:
        text = win32gui.GetWindowText(hwnd) or ''
        if needle in text.lower():
            vis = win32gui.IsWindowVisible(hwnd)
            cls = win32gui.GetClassName(hwnd)
            tid, pid = win32process.GetWindowThreadProcessId(hwnd)
            matches.append((hwnd, text, vis, cls, pid))
    except Exception:
        pass
    return True

win32gui.EnumWindows(enum, None)

if not matches:
    print(f'No windows found matching: {args.match!r}')
else:
    print(f'Found {len(matches)} window(s) matching: {args.match!r}')
    for hwnd, text, vis, cls, pid in matches:
        print(f'HWND={hwnd:#010x} | visible={vis} | pid={pid} | class={cls} | title={text}')
