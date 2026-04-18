# 🚀 OCR VNCV: Giải pháp nhận dạng hóa đơn Tiếng Việt chuyên sâu

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**OCR VNCV** là một hệ thống nhận dạng ký tự quang học mạnh mẽ, được tối ưu hóa đặc biệt cho tiếng Việt và các loại hóa đơn bán lẻ (Receipts). Project tích hợp giữa engine OCR AI tiên tiến và giao diện Dashboard hiện đại, giúp việc trích xuất dữ liệu trở nên nhanh chóng và chính xác.

---

## 📸 Demo & Giao diện

### Web Dashboard
Giao diện trực quan hỗ trợ kéo thả ảnh, xem trước và hiển thị kết quả trích xuất theo thời gian thực.
![Web Dashboard](file:///c:/Users/Phucc/Desktop/job/M%E1%BA%A1nh/img_demo/UI.png)

### Kết quả nhận dạng mẫu
Hệ thống xử lý tốt các loại hóa đơn in nhiệt, chữ mờ hoặc ảnh chụp trong điều kiện ánh sáng không lý tưởng.
![OCR Test](file:///c:/Users/Phucc/Desktop/job/M%E1%BA%A1nh/img_demo/test.png)

---

## ✨ Tính năng nổi bật

- **🔤 Tối ưu Tiếng Việt:** Xử lý chính xác các ký tự có dấu, font chữ hóa đơn đặc thù và các cấu trúc văn bản hành chính Việt Nam.
- **⚙️ Pipeline Dual-Mode (Thông minh):** 
  - **Standard Mode:** Ưu tiên tốc độ, xử lý ảnh chất lượng tốt.
  - **Aggressive Mode:** Tự động kích hoạt khi ảnh mờ/nhiễu, áp dụng bộ lọc tăng cường độ tương phản và binarization để cứu vãn thông tin.
- **🖼️ Tiền xử lý ảnh nâng cao:** Tích hợp Unsharp Mask, Autocontrast, Resizing thông minh giúp cải thiện đáng kể tỷ lệ nhận diện.
- **🌐 RESTful API:** Cung cấp endpoint dễ dàng tích hợp vào các hệ thống quản lý tài chính hoặc ứng dụng di động.
- **⚡ Hiệu năng cao:** Tối ưu hóa thời gian phản hồi (average ~5s trên CPU) nhờ cơ chế warm-up model và xử lý bất đồng bộ.

---

## 🛠️ Cài đặt & Triển khai

### 1. Yêu cầu hệ thống
- Python 3.10 trở lên.
- Thư viện `vncv` (đã được cấu hình trong `requirements.txt`).

### 2. Cài đặt chi tiết
```bash
# Clone project và đi vào thư mục
# cd OCR_VNCV

# Tạo và kích hoạt môi trường ảo
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate # Linux/Mac

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt
```

### 3. Khởi chạy
Chạy server FastAPI:
```bash
# Chạy trực tiếp qua main.py
python main.py

# Hoặc dùng uvicorn thủ công
python -m uvicorn main:app --reload --port 8000
```
Truy cập Dashboard tại: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 🔌 API Documentation

### OCR Endpoint
`POST /api/ocr`

**Request:** `multipart/form-data` với field `file` (ảnh JPEG, PNG, WEBP).

**Response:**
```json
{
  "text": "TÊN CỬA HÀNG\nĐỊA CHỈ: ...\nSỐ TIỀN: 50.000 VNĐ",
  "confidence": 0.8945,
  "mode": "standard",
  "elapsed_ms": 1205.4,
  "char_count": 145
}
```

---

## 📁 Cấu trúc thư mục chính

- `main.py`: Entry point, khởi tạo ứng dụng và mount router.
- `ocr.py`: Trái tim của hệ thống - Chứa logic tiền xử lý và pipeline OCR vncv.
- `router.py`: Định nghĩa các API endpoints và phục vụ static files cho Dashboard.
- `web/`: Toàn bộ mã nguồn giao diện (HTML/CSS/JS).
- `config.py`: Các tham số tinh chỉnh (Threshold, Contrast, Resize limits).
- `img_demo/`: Chứa các hình ảnh minh họa cho README.

---

## 👤 Tác giả
Dự án được phát triển bởi **Phuc710**. 

---
*Ghi chú: Project này được xây dựng phục vụ mục đích học tập và nghiên cứu công nghệ OCR tại Việt Nam.*
