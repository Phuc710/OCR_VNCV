# Phân Tích Các Giai Đoạn Xử Lý – Pipeline OCR (VNCV)

Hệ thống nhận dạng văn bản (OCR) được xây dựng theo quy trình xử lý **5 giai đoạn** được phân tách rõ ràng trong `ocr.py`. Kiến trúc tuân theo nguyên tắc **single-responsibility**: mỗi hàm đảm nhận đúng một nhiệm vụ, dễ kiểm thử và bảo trì. Ngôn ngữ đích: **Tiếng Việt** (`OCR_LANG = "vi"`, thư viện `vncv`).

---

## Sơ Đồ Tổng Quan Luồng Xử Lý

```
📤 HTTP POST /api/ocr  (upload file ảnh)
        │
        ▼
┌─────────────────────────┐
│  Giai đoạn 0            │  Model warm-up (background thread)
│  Khởi động Model        │  _do_warmup() → _vncv_extract ready
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Giai đoạn 1            │  router.py → Image.open()
│  Thu nhận ảnh đầu vào   │  Decode bytes → PIL.Image RGB
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Giai đoạn 2            │  _preprocess() → standard / aggressive
│  Tiền xử lý ảnh         │  Grayscale + Contrast + Resize
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Giai đoạn 3            │  _vncv_extract(tmp_path, lang="vi")
│  OCR Engine (VNCV)      │  → list[dict{text, confidence}]
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Giai đoạn 4            │  _clean(items) → lọc rác + dedup
│  Lọc & Làm Sạch         │  → (text: str, confidence: float)
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Giai đoạn 5            │  extract_text() → auto-retry logic
│  Chuẩn Hóa Đầu Ra       │  OCRResult → JSON response
└─────────────────────────┘
         │
         ▼
📥 JSON { text, confidence, mode, elapsed_ms, char_count }
```

---

## Giai Đoạn 0 – Khởi Động Model (Warm-up)

Mô hình OCR (`vncv`) có độ trễ khởi tạo lớn ở lần gọi đầu tiên do phải load weights ONNX vào bộ nhớ. Để tránh người dùng phải chờ khi gửi ảnh lần đầu, hệ thống thực hiện **warm-up không đồng bộ** trong một **daemon thread** ngay khi module được import.

Quá trình warm-up:
1. Tạo ảnh giả `64×64` pixel trắng (dummy image).
2. Lưu tạm vào `tempfile` rồi gọi `_vncv_extract()` một lần.
3. Set `threading.Event(_warmup_done)` để báo hiệu hoàn tất.

Các lần gọi OCR thật sau đó sẽ `wait()` trên Event này (tối đa `WARMUP_TIMEOUT = 30s`), đảm bảo model luôn sẵn sàng.

**Code trọng tâm – `ocr.py`:**

```python
_warmup_done  = threading.Event()
_vncv_extract = None   # Hàm extract_text từ thư viện vncv, khởi tạo lazy

def _do_warmup() -> None:
    global _vncv_extract
    try:
        with _silence():                          # Tắt log noise từ ONNX/TF
            from vncv import extract_text as _fn
            _vncv_extract = _fn
            # Tạo ảnh giả để "hâm nóng" model
            dummy = Image.new("RGB", (64, 64), color=255)
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                dummy.save(f, format="JPEG")
                p = f.name
            _fn(p, lang=config.OCR_LANG, return_dict=True)   # Lần gọi đầu = warm-up
            os.remove(p)
    except Exception:
        pass   # Warm-up fail không crash app
    finally:
        _warmup_done.set()   # Báo hiệu cho các thread khác biết model đã sẵn sàng

# Chạy ngay khi import module (daemon = tự tắt khi app thoát)
threading.Thread(target=_do_warmup, daemon=True, name="ocr-warmup").start()
```

> **Thiết kế đáng chú ý:** `_silence()` là context manager dùng `os.dup2()` để redirect cả `stderr` ở cấp C-extension (không chỉ Python), giúp chặn hoàn toàn log noise từ ONNX Runtime và TensorFlow mà các `contextlib.redirect_stderr()` thông thường không làm được.

---

## Giai Đoạn 1 – Thu Nhận Ảnh Đầu Vào (Input)

Ảnh được gửi qua `HTTP POST /api/ocr` dưới dạng `multipart/form-data`. `router.py` đảm nhận việc validate và decode ảnh trước khi đưa vào pipeline OCR.

Hệ thống kiểm tra `Content-Type` phải là `image/*`, sau đó dùng **Pillow** để decode bytes thành `PIL.Image` và ép về chế độ màu `RGB` (thống nhất đầu vào, loại bỏ alpha channel của PNG).

**Code trọng tâm – `router.py`:**

```python
@ocr_router.post("/ocr")
async def ocr_endpoint(file: UploadFile = File(...)) -> dict:
    # Bước 1: Validate Content-Type
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="File must be an image")

    raw = await file.read()   # Đọc toàn bộ bytes của file upload

    # Bước 2: Decode bytes → PIL.Image
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        # .convert("RGB"): chuẩn hóa sang 3 kênh, xử lý được cả PNG có alpha
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Cannot decode image: {e}")

    print(f"[API] Bắt đầu nhận dạng ảnh: {file.filename} (Kích thước: {img.size})")

    # Bước 3: Gọi pipeline OCR
    result: OCRResult = extract_text(img)
```

**Định dạng ảnh hỗ trợ:** JPEG, PNG, WEBP, BMP (bất kỳ định dạng nào Pillow đọc được).

---

## Giai Đoạn 2 – Tiền Xử Lý Ảnh (Preprocessing)

Đây là giai đoạn quan trọng nhất quyết định chất lượng OCR. Hệ thống có **hai chế độ tiền xử lý** tương ứng với hai mức độ xử lý:

### 2a – Chế Độ Standard (Mặc định)

| Bước | Kỹ thuật | Tham số |
|------|---------|---------|
| Grayscale | `img.convert("L")` | — |
| Auto Contrast | `ImageOps.autocontrast(cutoff=1)` | `STANDARD_CONTRAST_CUTOFF = 1` |
| Sharpening | `UnsharpMask` | radius=1.5, percent=120, threshold=3 |
| Resize | `_resize()` | Min 640px, Max 1280px cạnh dài |
| Convert back | `.convert("RGB")` | Trả về RGB cho VNCV |

### 2b – Chế Độ Aggressive (Khi Standard yếu)

Được kích hoạt tự động khi confidence của Standard mode thấp hơn `CONF_THRESHOLD = 0.40` hoặc ít hơn `MIN_CHARS = 30` ký tự:

| Bước | Kỹ thuật | Tham số |
|------|---------|---------|
| Grayscale | `img.convert("L")` | — |
| Auto Contrast | `autocontrast(cutoff=0)` | Không cắt histogram |
| Contrast Boost | `ImageEnhance.Contrast` | Factor = **2.5x** |
| Binarization | `img.point(lambda px: 0 if px < 128 else 255)` | `AGGRESSIVE_BINARIZE_THR = 128` |
| Resize | `_resize()` | Min 640px, Max 1280px |

### Logic Resize Thông Minh (`_resize`)

```python
def _resize(img: Image.Image) -> Image.Image:
    w, h = img.size
    long_s, short_s = max(w, h), min(w, h)
    if long_s > config.MAX_SIDE:        # Ảnh quá lớn → thu nhỏ
        scale = config.MAX_SIDE / long_s
    elif short_s < config.MIN_SIDE:     # Ảnh quá nhỏ → phóng to
        scale = config.MIN_SIDE / short_s
        if max(w * scale, h * scale) > config.MAX_SIDE * 1.5:
            return img                  # Tránh phóng to quá mức (bảo toàn tỉ lệ)
    else:
        return img                      # Đã trong ngưỡng → giữ nguyên
    return img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
```

**Code trọng tâm – `ocr.py`:**

```python
def _preprocess(img: Image.Image, aggressive: bool = False) -> Image.Image:
    cutoff = 0 if aggressive else config.STANDARD_CONTRAST_CUTOFF   # 0 hoặc 1
    gray = ImageOps.autocontrast(img.convert("L"), cutoff=cutoff)

    if aggressive:
        # Chế độ mạnh: tăng contrast cực đại + nhị phân hóa
        gray = ImageEnhance.Contrast(gray).enhance(config.AGGRESSIVE_CONTRAST)  # 2.5x
        gray = gray.point(lambda px: 0 if px < config.AGGRESSIVE_BINARIZE_THR else 255)
    else:
        # Chế độ chuẩn: làm nét bằng UnsharpMask (giữ gradient)
        gray = gray.filter(ImageFilter.UnsharpMask(
            radius=config.UNSHARP_RADIUS,       # 1.5
            percent=config.UNSHARP_PERCENT,     # 120
            threshold=config.UNSHARP_THRESHOLD, # 3
        ))
    return _resize(gray).convert("RGB")   # Scale về kích thước hợp lý
```

---

## Giai Đoạn 3 – OCR Engine (VNCV)

Sau khi tiền xử lý, ảnh được lưu tạm vào **tempfile** trên ổ đĩa (do VNCV yêu cầu đường dẫn file, không nhận binary stream), sau đó engine OCR được gọi để trích xuất text.

Hàm `_vncv_extract(tmp, lang="vi", return_dict=True)` trả về danh sách các item, mỗi item là một `dict` chứa:

```python
{
    "text":       "Nội dung dòng văn bản",
    "confidence": 0.87   # float 0.0 – 1.0
}
```

Toàn bộ quá trình được bọc trong `_silence()` để che các log noise từ thư viện C/ONNX Runtime ra console.

**Code trọng tâm – `ocr.py`:**

```python
def _run(img: Image.Image, aggressive: bool = False) -> OCRResult:
    tmp = None
    t0  = time.perf_counter()
    try:
        # Chờ warm-up xong (tối đa WARMUP_TIMEOUT = 30 giây)
        _warmup_done.wait(timeout=config.WARMUP_TIMEOUT)
        if _vncv_extract is None:               # Fallback nếu warm-up chưa kịp chạy
            with _silence():
                from vncv import extract_text as _fn
                _vncv_extract = _fn

        # Tiền xử lý ảnh (standard hoặc aggressive)
        processed = _preprocess(img, aggressive)

        # Lưu ảnh đã xử lý vào tempfile để engine đọc
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            processed.save(f, format="JPEG", quality=config.OCR_QUALITY)  # quality=85
            tmp = f.name

        # Gọi engine OCR (tiếng Việt, trả dict)
        with _silence():
            items = _vncv_extract(tmp, lang=config.OCR_LANG, return_dict=True) or []

        text, conf = _clean(items)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return OCRResult(text=text, confidence=conf, mode=mode, elapsed_ms=round(elapsed_ms, 1))
    finally:
        # Dọn sạch tempfile dù thành công hay thất bại
        if tmp and os.path.exists(tmp):
            os.remove(tmp)
```

---

## Giai Đoạn 4 – Lọc và Làm Sạch Văn Bản (Text Cleaning)

Kết quả thô từ OCR engine thường chứa nhiễu: ký tự rác, dòng trùng lặp, nhãn logo, ký tự đặc biệt vô nghĩa. Hàm `_clean()` áp dụng **4 lớp lọc** tuần tự:

| Lớp lọc | Điều kiện loại bỏ | Regex / Logic |
|---------|------------------|---------------|
| **Rác ký tự** | Dòng chỉ gồm ≤ 3 ký tự không phải chữ/số | `^[^\w\d]{0,3}$` |
| **Không có chữ/số** | Dòng không chứa bất kỳ `\w` nào | `re.search(r"[\w\d]", ln)` |
| **Logo ngắn** | Chuỗi 2–8 ký tự không dấu cách, không có số | `^\S{2,8}$` + no digit |
| **Trùng lặp (Dedup)** | Cùng nội dung (lowercase, bỏ khoảng trắng) | Sliding window `DEDUP_WINDOW = 20` |

Sau khi lọc, các dòng còn lại được nối bằng `\n` và tính **confidence trung bình** từ toàn bộ dòng hợp lệ.

**Code trọng tâm – `ocr.py`:**

```python
_JUNK = re.compile(r"^[^\w\d]{0,3}$", re.UNICODE)  # ≤3 ký tự rác
_LOGO = re.compile(r"^\S{2,8}$")                    # Chuỗi ngắn không dấu cách

def _clean(raw_items: list) -> tuple[str, float]:
    lines, confs, seen = [], [], set()
    for item in raw_items:
        ln   = str(item.get("text", "") if isinstance(item, dict) else item).strip()
        conf = float(item.get("confidence", 0)) if isinstance(item, dict) else 0.0

        if not ln or _JUNK.match(ln):                       # Lọc 1: ký tự rác
            continue
        if not re.search(r"[\w\d]", ln, re.UNICODE):        # Lọc 2: không có chữ/số
            continue
        if _LOGO.match(ln) and not re.search(r"\d", ln):    # Lọc 3: logo ngắn
            continue

        # Lọc 4: Dedup bằng sliding window
        key = re.sub(r"\s+", "", ln.lower())                # Chuẩn hóa key
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > config.DEDUP_WINDOW:                 # Giữ cửa sổ 20 key
            seen.pop()

        lines.append(re.sub(r" {2,}", " ", ln))             # Nén khoảng trắng thừa
        confs.append(conf)

    text = "\n".join(lines)
    avg  = sum(confs) / len(confs) if confs else 0.0
    return text, avg
```

---

## Giai Đoạn 5 – Chuẩn Hóa Đầu Ra & Auto-Retry (Output)

Đây là **lớp quyết định cuối cùng** của pipeline. Hàm `extract_text()` (Public API) tự động thử lại với chế độ `aggressive` nếu kết quả `standard` không đủ tốt.

### Logic Auto-Retry

```
extract_text(img)
    │
    ├── Chạy _run(img, aggressive=False)  →  result_standard
    │
    ├── Kết quả đủ tốt?
    │     • KHÔNG có lỗi
    │     • confidence ≥ 0.40  (CONF_THRESHOLD)
    │     • độ dài ≥ 30 chars  (MIN_CHARS)
    │         │
    │         └─ ✅ TRẢ VỀ result_standard ngay
    │
    └── Kết quả yếu → Chạy _run(img, aggressive=True)  →  result_aggressive
            │
            ├── r2.confidence > r.confidence     → Dùng aggressive
            ├── len(r2.text) > len(r.text) * 1.2 → Dùng aggressive (nhiều text hơn 20%)
            └── Ngược lại                        → Giữ standard (tránh overprocess)
```

**Code trọng tâm – `ocr.py`:**

```python
def extract_text(img: Image.Image) -> OCRResult:
    """Run OCR, auto-retry with aggressive preprocessing if standard is weak."""
    r = _run(img)   # Thử chế độ standard trước

    # Kiểm tra xem kết quả đã đủ tốt chưa
    if r.error or (r.confidence >= config.CONF_THRESHOLD and len(r.text) >= config.MIN_CHARS):
        return r   # Đủ tốt → trả về ngay

    # Kết quả yếu → thử lại với aggressive preprocessing
    log.info(f"Weak result (conf={r.confidence:.2f}, chars={len(r.text)}) → trying aggressive")
    r2 = _run(img, aggressive=True)

    # So sánh hai kết quả, chọn cái tốt hơn
    return r2 if (r2.confidence > r.confidence or len(r2.text) > len(r.text) * 1.2) else r
```

### Cấu Trúc Dữ Liệu Đầu Ra

```python
@dataclass(slots=True)
class OCRResult:
    text:       str            # Văn bản đã làm sạch
    confidence: float          # Độ tin cậy trung bình (0.0 – 1.0)
    mode:       str            # "standard" | "aggressive"
    elapsed_ms: float          # Thời gian xử lý (ms)
    error:      Optional[str]  # None nếu thành công
```

**JSON Response từ API (`router.py`):**

```json
{
    "text":       "Nội dung văn bản trích xuất...",
    "confidence": 0.8732,
    "mode":       "standard",
    "elapsed_ms": 423.5,
    "char_count": 156
}
```

---

## Tổng Kết Các Tham Số Cấu Hình (`config.py`)

| Tham số | Giá trị | Ý nghĩa |
|---------|---------|---------|
| `CONF_THRESHOLD` | `0.40` | Ngưỡng confidence tối thiểu để chấp nhận kết quả standard |
| `MIN_CHARS` | `30` | Số ký tự tối thiểu để coi là kết quả đủ tốt |
| `MIN_SIDE` | `640 px` | Scale up nếu cạnh ngắn nhỏ hơn giá trị này |
| `MAX_SIDE` | `1280 px` | Scale down nếu cạnh dài lớn hơn giá trị này |
| `STANDARD_CONTRAST_CUTOFF` | `1` | Cắt histogram autocontrast ở chế độ standard |
| `AGGRESSIVE_CONTRAST` | `2.5` | Hệ số tăng contrast ở chế độ aggressive |
| `AGGRESSIVE_BINARIZE_THR` | `128` | Ngưỡng nhị phân hóa pixel (0–255) |
| `UNSHARP_RADIUS` | `1.5` | Bán kính kernel UnsharpMask |
| `UNSHARP_PERCENT` | `120` | Cường độ làm nét (%) |
| `UNSHARP_THRESHOLD` | `3` | Ngưỡng tương phản tối thiểu để áp dụng làm nét |
| `OCR_LANG` | `"vi"` | Ngôn ngữ nhận dạng: Tiếng Việt |
| `OCR_QUALITY` | `85` | Chất lượng JPEG khi lưu tempfile cho engine |
| `WARMUP_TIMEOUT` | `30 s` | Thời gian tối đa chờ model warm-up |
| `DEDUP_WINDOW` | `20` | Kích thước sliding window khử trùng lặp |

> **Lưu ý thiết kế:** Toàn bộ tham số được tách biệt hoàn toàn vào `config.py`. Khi cần tinh chỉnh cho một loại ảnh/domain cụ thể (ví dụ: ảnh chụp menu nhà hàng vs. biển số xe), chỉ cần sửa `config.py` mà không cần đụng vào logic xử lý.
