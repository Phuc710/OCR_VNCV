# config.py — All tunable constants for the OCR pipeline

# ── OCR Quality Thresholds ────────────────────────────────
CONF_THRESHOLD = 0.40   # min confidence to accept standard result
MIN_CHARS      = 30     # min characters to consider a good result
MIN_SIDE       = 640    # scale up if shortest side < this
MAX_SIDE       = 1280   # scale down if longest side > this

# ── Image Preprocessing ───────────────────────────────────
STANDARD_CONTRAST_CUTOFF = 1      # autocontrast cutoff (standard mode)
AGGRESSIVE_CONTRAST      = 2.5    # contrast enhance factor (aggressive)
AGGRESSIVE_BINARIZE_THR  = 128    # pixel threshold for binarization
UNSHARP_RADIUS           = 1.5
UNSHARP_PERCENT          = 120
UNSHARP_THRESHOLD        = 3

# ── OCR Engine ────────────────────────────────────────────
OCR_LANG     = "vi"
OCR_QUALITY  = 85       # JPEG quality when writing temp file
WARMUP_TIMEOUT = 30     # seconds to wait for model warmup

# ── Dedup sliding window ──────────────────────────────────
DEDUP_WINDOW = 20       # keep last N unique line keys for dedup
