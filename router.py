"""
router.py — FastAPI router for the OCR API.
Mount this into your main app:
    app.include_router(ocr_router)
"""
from __future__ import annotations

import io
import time
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from ocr import OCRResult, extract_text

ocr_router = APIRouter(prefix="/api", tags=["OCR"])
WEB_DIR = Path(__file__).parent / "web"


# ── POST /api/ocr ─────────────────────────────────────────────────────────────
@ocr_router.post("/ocr")
async def ocr_endpoint(file: UploadFile = File(...)) -> dict:
    """
    Upload an image, get back OCR text + confidence + timing.
    Accepts: JPEG, PNG, WEBP, BMP
    """
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="File must be an image")

    raw = await file.read()
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        print(f"[API] Error decoding image: {e}")
        raise HTTPException(status_code=422, detail=f"Cannot decode image: {e}")

    print(f"\n[API] Bắt đầu nhận dạng ảnh: {file.filename} (Kích thước: {img.size})")
    
    t0 = time.time()
    result: OCRResult = extract_text(img)
    t1 = time.time()

    if result.error:
        print(f"[API] Lỗi OCR: {result.error}")
        raise HTTPException(status_code=500, detail=result.error)

    print(f"[API] Xử lý thành công trong {result.elapsed_ms}ms (Mode: {result.mode})")
    print(f"[API] Kết quả trích xuất ({len(result.text)} ký tự, Độ tự tin: {result.confidence:.2f}):\n{'-'*40}\n{result.text[:100]}...\n{'-'*40}")

    return {
        "text":        result.text,
        "confidence":  round(result.confidence, 4),
        "mode":        result.mode,
        "elapsed_ms":  result.elapsed_ms,
        "char_count":  len(result.text),
    }


# ── GET /api/health ───────────────────────────────────────────────────────────
@ocr_router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ocr"}


# ── Serve web dashboard (index.html) ──────────────────────────────────────────
def mount_web(app) -> None:
    """Call after creating your FastAPI app: mount_web(app)"""
    if WEB_DIR.exists():
        app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        html_path = WEB_DIR / "index.html"
        if not html_path.exists():
            return HTMLResponse("<h1>Web folder not found</h1>", status_code=404)
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
