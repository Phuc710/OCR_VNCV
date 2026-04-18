
"""
ocr.py — VNCV OCR pipeline (standalone, no extra project deps).
Public API:
    result = extract_text(img: PIL.Image.Image) -> OCRResult
    result.text        # cleaned string
    result.confidence  # float 0-1
    result.mode        # "standard" | "aggressive"
    result.elapsed_ms  # float, inference time in ms
"""
from __future__ import annotations
import logging
import os
import re
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

import config

log = logging.getLogger("ocr")


# ── Suppress ONNX / TF C++ stderr noise ──────────────────────────────────────
@contextmanager
def _silence():
    os.environ.setdefault("ORT_LOGGING_LEVEL", "3")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    sys.stderr.flush()
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    saved_err  = os.dup(2)
    saved_out, saved_err_py = sys.stdout, sys.stderr
    try:
        os.dup2(devnull_fd, 2)
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
        yield
    finally:
        sys.stdout.close(); sys.stderr.close()
        sys.stdout, sys.stderr = saved_out, saved_err_py
        os.dup2(saved_err, 2)
        os.close(devnull_fd); os.close(saved_err)


# ── Model warm-up (background, avoids first-call delay) ──────────────────────
_warmup_done  = threading.Event()
_vncv_extract = None

def _do_warmup() -> None:
    global _vncv_extract
    try:
        with _silence():
            from vncv import extract_text as _fn
            _vncv_extract = _fn
            dummy = Image.new("RGB", (64, 64), color=255)
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                dummy.save(f, format="JPEG")
                p = f.name
            _fn(p, lang=config.OCR_LANG, return_dict=True)
            os.remove(p)
    except Exception:
        pass
    finally:
        _warmup_done.set()

threading.Thread(target=_do_warmup, daemon=True, name="ocr-warmup").start()


# ── Result dataclass ──────────────────────────────────────────────────────────
@dataclass(slots=True)
class OCRResult:
    text:       str
    confidence: float
    mode:       str            = "standard"   # "standard" | "aggressive"
    elapsed_ms: float          = 0.0
    error:      Optional[str]  = None


# ── Image preprocessing ───────────────────────────────────────────────────────
def _resize(img: Image.Image) -> Image.Image:
    w, h = img.size
    long_s, short_s = max(w, h), min(w, h)
    if long_s > config.MAX_SIDE:
        scale = config.MAX_SIDE / long_s
    elif short_s < config.MIN_SIDE:
        scale = config.MIN_SIDE / short_s
        if max(w * scale, h * scale) > config.MAX_SIDE * 1.5:
            return img
    else:
        return img
    return img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)


def _preprocess(img: Image.Image, aggressive: bool = False) -> Image.Image:
    cutoff = 0 if aggressive else config.STANDARD_CONTRAST_CUTOFF
    gray = ImageOps.autocontrast(img.convert("L"), cutoff=cutoff)
    if aggressive:
        gray = ImageEnhance.Contrast(gray).enhance(config.AGGRESSIVE_CONTRAST)
        gray = gray.point(lambda px: 0 if px < config.AGGRESSIVE_BINARIZE_THR else 255)
    else:
        gray = gray.filter(ImageFilter.UnsharpMask(
            radius=config.UNSHARP_RADIUS,
            percent=config.UNSHARP_PERCENT,
            threshold=config.UNSHARP_THRESHOLD,
        ))
    return _resize(gray).convert("RGB")


# ── Text cleaning ─────────────────────────────────────────────────────────────
_JUNK = re.compile(r"^[^\w\d]{0,3}$", re.UNICODE)
_LOGO = re.compile(r"^\S{2,8}$")

def _clean(raw_items: list) -> tuple[str, float]:
    lines, confs, seen = [], [], set()
    for item in raw_items:
        ln   = str(item.get("text", "") if isinstance(item, dict) else item).strip()
        conf = float(item.get("confidence", 0)) if isinstance(item, dict) else 0.0
        if not ln or _JUNK.match(ln):
            continue
        if not re.search(r"[\w\d]", ln, re.UNICODE):
            continue
        if _LOGO.match(ln) and not re.search(r"\d", ln):
            continue
        key = re.sub(r"\s+", "", ln.lower())
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > config.DEDUP_WINDOW:
            seen.pop()
        lines.append(re.sub(r" {2,}", " ", ln))
        confs.append(conf)
    text = "\n".join(lines)
    avg  = sum(confs) / len(confs) if confs else 0.0
    return text, avg


# ── Core OCR runner ───────────────────────────────────────────────────────────
def _run(img: Image.Image, aggressive: bool = False) -> OCRResult:
    global _vncv_extract
    mode = "aggressive" if aggressive else "standard"
    tmp  = None
    t0   = time.perf_counter()
    try:
        _warmup_done.wait(timeout=config.WARMUP_TIMEOUT)
        if _vncv_extract is None:
            with _silence():
                from vncv import extract_text as _fn
                _vncv_extract = _fn

        processed = _preprocess(img, aggressive)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            processed.save(f, format="JPEG", quality=config.OCR_QUALITY)
            tmp = f.name

        with _silence():
            items = _vncv_extract(tmp, lang=config.OCR_LANG, return_dict=True) or []

        text, conf = _clean(items)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return OCRResult(text=text, confidence=conf, mode=mode, elapsed_ms=round(elapsed_ms, 1))

    except ImportError as e:
        return OCRResult("", 0.0, mode, error=f"vncv not installed: {e}")
    except Exception as e:
        log.exception(f"OCR failed ({mode})")
        return OCRResult("", 0.0, mode, error=str(e)[:300])
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)


# ── Public API ────────────────────────────────────────────────────────────────
def extract_text(img: Image.Image) -> OCRResult:
    """Run OCR, auto-retry with aggressive preprocessing if standard is weak."""
    r = _run(img)
    if r.error or (r.confidence >= config.CONF_THRESHOLD and len(r.text) >= config.MIN_CHARS):
        return r
    log.info(f"Weak result (conf={r.confidence:.2f}, chars={len(r.text)}) → trying aggressive")
    r2 = _run(img, aggressive=True)
    return r2 if (r2.confidence > r.confidence or len(r2.text) > len(r.text) * 1.2) else r


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    path = sys.argv[1] if len(sys.argv) > 1 else "222.jpg"
    img  = Image.open(path)
    res  = extract_text(img)

    if res.error:
        print(f"[FAIL] {res.error}")
        sys.exit(1)

    print(f"[OK] mode={res.mode} | conf={res.confidence:.2f} | {res.elapsed_ms:.0f}ms")
    print("-" * 40)
    print(res.text)
    print("-" * 40)
