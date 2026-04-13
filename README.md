# OCR VNCV Dashboard 🚀

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)

Một giải pháp nhận dạng ký tự quang học (OCR) chuyên biệt cho Tiếng Việt, tập trung vào việc trích xuất dữ liệu từ các dòng hóa đơn bán lẻ (Receipts). Hệ thống đi kèm với Dashboard quản lý trực quan và API hiệu năng cao.

## ✨ Tính năng nổi bật

- **Nhận diện Tiếng Việt chuyên sâu:** Tối ưu hóa cho các font chữ hóa đơn in nhiệt và văn bản hành chính.
- **Pipeline xử lý thông minh:** Tự động điều chỉnh giữa hai chế độ xử lý **Standard** (Tiêu chuẩn) và **Aggressive** (Nâng cao) dựa trên độ tin cậy của ảnh.
- **Tiền xử lý nâng cao:** Tích hợp bộ lọc khử nhiễu, tăng độ tương phản và tự động cân chỉnh hướng ảnh.
- **Web Dashboard:** Giao diện kéo thả hiện đại, hỗ trợ xem trước ảnh và hiển thị kết quả thời gian thực.

## 📊 Hiệu năng thực tế (Benchmarks)

Dựa trên kết quả thực nghiệm với 4 mẫu hóa đơn đại diện (`cafe.png`, `image.png`, `3.png`, `222.jpg`):

| Chỉ số | Kết quả trung bình | Đánh giá |
| :--- | :--- | :--- |
| **Độ tin cậy (Confidence)** | **83.72%** | Hoạt động tốt trên cả ảnh chất lượng trung bình |
| **Tốc độ xử lý (Latency)** | **5.37 giây** | Phản hồi nhanh trên môi trường CPU |
| **Độ chính xác (Accuracy)** | **91.5%** | Tỉ lệ trích xuất đúng các trường thông tin chính |

## 🛠️ Cài đặt & Chạy ứng dụng

### 1. Cài đặt môi trường
Đảm bảo bạn đã cài đặt Python 3.10 trở lên.
```bash
# Tạo môi trường ảo (Khuyến khích)
python -m venv venv
source venv/bin/activate  # Trên Linux/Mac
.\venv\Scripts\activate   # Trên Windows

# Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt
```

### 2. Chạy ứng dụng
Khởi động Backend FastAPI:
```bash
python main.py
```
Ứng dụng sẽ chạy tại địa chỉ: `http://127.0.0.1:8000`

## 📁 Cấu trúc dự án

- `main.py`: Điểm khởi đầu của ứng dụng FastAPI.
- `ocr.py`: Pipeline xử lý OCR và Tiền xử lý ảnh.
- `router.py`: Định nghĩa các API endpoints.
- `config.py`: Các tham số cấu hình hệ thống.
- `web/`: Chứa mã nguồn Giao diện Dashboard (HTML/CSS/JS).
- `chapter_4_report.md`: Báo cáo thực nghiệm chi tiết.

## 🤝 Autor
Dự án được thực hiện bởi **Phuc710**.

---
*Dữ liệu và mã nguồn được đóng gói phục vụ cho mục đích nghiên cứu và đào tạo.*
