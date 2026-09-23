import time, random, traceback
from pathlib import Path

import pyautogui
from mss import mss
from PIL import Image
import imagehash

# ===================== CONFIG =====================
# Skip button coordinates
SKIP_XY = (2467, 1472)

# Rectangle for random clicking (TOP-LEFT and BOTTOM-RIGHT)
TL_X, TL_Y = 750, 338
BR_X, BR_Y = 2457, 1305

# Try Skip every N seconds
CLICK_INTERVAL_SEC = 3

# Page-change detection (bigger threshold = stricter “changed”)
HASH_DIFF_THRESHOLD = 6  # 0–3 identical, 10+ definitely changed

# Spam settings
SPAM_CLICKS_PER_SEC   = 20   # target actions per second during spam
SPAM_BURST_SECONDS    = 3    # burst duration before retrying Skip
MAX_SPAM_CYCLES       = 30   # safety cap

# Drag behavior
DRAG_DURATION_RANGE   = (0.08, 0.20)  # seconds per drag
DRAG_HOLD_BEFORE_MOVE = 0.02          # optional mouseDown hold
# Optional: compare only a region (left, top, width, height); None = full screen
REGION = None
# Safety: move mouse to top-left corner to abort at any time
pyautogui.PAUSE = 0.02
pyautogui.FAILSAFE = True

OUT_DIR = Path.cwd() / "captures"
OUT_DIR.mkdir(exist_ok=True)
# ==================================================


def screenshot(path: Path, region=None):
    """Save a PNG screenshot to `path`. Region = (l,t,w,h) or None for full desktop."""
    with mss() as sct:
        if region is None:
            grab = sct.grab(sct.monitors[0])
        else:
            l, t, w, h = region
            grab = sct.grab({"left": l, "top": t, "width": w, "height": h})
        Image.frombytes("RGB", grab.size, grab.bgra, "raw", "BGRX").save(path)


def image_hash_diff(a: Path, b: Path) -> int:
    """Perceptual difference between two screenshots (lower = more similar)."""
    h1 = imagehash.dhash(Image.open(a).convert("RGB"))
    h2 = imagehash.dhash(Image.open(b).convert("RGB"))
    return abs(h1 - h2)


def page_changed(before: Path, after: Path) -> bool:
    """Return True if the page looks different after the action."""
    diff = image_hash_diff(before, after)
    print(f"[INFO] diff={diff} (thr={HASH_DIFF_THRESHOLD})")
    return diff > HASH_DIFF_THRESHOLD


def attempt_skip() -> bool:
    """Click Skip once; return True if page changed, else False."""
    before = OUT_DIR / "before.png"
    after  = OUT_DIR / "after.png"
    screenshot(before, REGION)
    pyautogui.click(*SKIP_XY)
    time.sleep(1.0)  # give UI a moment to react
    screenshot(after, REGION)
    if page_changed(before, after):
        print("[OK] Skip succeeded.")
        return True
    print("[WARN] Skip didn’t seem to work.")
    return False


def _rand_point_in_rect():
    min_x, max_x = sorted((TL_X, BR_X))
    min_y, max_y = sorted((TL_Y, BR_Y))
    return random.randint(min_x, max_x), random.randint(min_y, max_y)


def _single_click_action():
    x, y = _rand_point_in_rect()
    pyautogui.click(x, y)


def _drag_click_action():
    sx, sy = _rand_point_in_rect()
    ex, ey = _rand_point_in_rect()
    dur = random.uniform(*DRAG_DURATION_RANGE)

    # Move to start, mouse down, short hold, drag to end, release
    pyautogui.moveTo(sx, sy)
    pyautogui.mouseDown()
    if DRAG_HOLD_BEFORE_MOVE > 0:
        time.sleep(DRAG_HOLD_BEFORE_MOVE)
    pyautogui.moveTo(ex, ey, duration=dur)
    pyautogui.mouseUp()


def spam_click_burst_alternating():
    """
    Rapid actions inside the rectangle for SPAM_BURST_SECONDS.
    Alternates: single click -> drag click -> single -> drag -> ...
    """
    print("[SPAM] Alternating single clicks and drag clicks in rectangle…")
    start = time.time()
    # Target actions per second; drag actions take a bit longer — alternation balances it.
    base_interval = 1.0 / max(1, SPAM_CLICKS_PER_SEC)

    toggle_drag = False  # start with single click first
    while time.time() - start < SPAM_BURST_SECONDS:
        if toggle_drag:
            _drag_click_action()
        else:
            _single_click_action()

        toggle_drag = not toggle_drag
        # Small base interval to keep throttle consistent
        time.sleep(base_interval)


def try_skip_with_fallback():
    """Attempt Skip; if it fails, spam (alt single/drag) until success or we hit MAX_SPAM_CYCLES."""
    if attempt_skip():
        return True
    print("[ACTION] Skip failed — starting spam mode.")
    for cycle in range(1, MAX_SPAM_CYCLES + 1):
        spam_click_burst_alternating()
        print(f"[RETRY] Trying Skip again (cycle {cycle}/{MAX_SPAM_CYCLES})…")
        if attempt_skip():
            print("[OK] Skip finally worked after spam.")
            return True
    print("[FAIL] Max spam cycles reached; moving on.")
    return False


def main():
    print("Auto-skipper: attempts every 3s; spams with alternating single/drag clicks if Skip fails.")
    print("Safety: move mouse to TOP-LEFT corner to abort.")
    while True:
        try:
            try_skip_with_fallback()
            time.sleep(CLICK_INTERVAL_SEC)
        except pyautogui.FailSafeException:
            print("[EXIT] Fail-safe triggered (mouse to top-left).")
            break
        except KeyboardInterrupt:
            print("[EXIT] Interrupted by user.")
            break
        except Exception:
            traceback.print_exc()
            time.sleep(2)


if __name__ == "__main__":
    main()
