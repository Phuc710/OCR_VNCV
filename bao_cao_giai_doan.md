# Phân Tích Các Giai Đoạn Xử Lý – Hệ Thống Giám Sát An Ninh CamAI

Hệ thống giám sát an ninh CamAI được xây dựng theo quy trình xử lý tuần tự gồm **6 giai đoạn chính**, tương ứng với **9 bước** được đánh dấu rõ ràng trong `video_generator()` của `main.py`. Mỗi giai đoạn đảm nhận một nhiệm vụ cụ thể, đảm bảo hệ thống hoạt động chính xác, ổn định và phản hồi theo thời gian thực.

---

## Sơ Đồ Tổng Quan Luồng Xử Lý

```
📷 Camera / File Video
        │
        ▼
┌─────────────────────┐
│  Giai đoạn 1        │  BƯỚC 1: Camera Stream
│  Thu nhận dữ liệu   │  cap.read() → frame
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Giai đoạn 2        │  BƯỚC 2: Tiền xử lý
│  Preprocessing      │  frame.copy() → disp_frame
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Giai đoạn 3        │  BƯỚC 3 & 4: Detect + Track
│  Detection &        │  model.track() → boxes, ids, confs
│  Tracking           │  (Frame skipping % 2)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Giai đoạn 4        │  BƯỚC 5: Duyệt từng đối tượng
│  ROI Processing     │  Point-in-Polygon Test (center)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Giai đoạn 5        │  BƯỚC 6, 7 & 8: Quyết định
│  Decision Making    │  hold_secs + cooldown → alert
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Giai đoạn 6        │  BƯỚC 9: Output
│  Output & Alert     │  MJPEG stream + Telegram + SSE
└─────────────────────┘
```

---

## Giai Đoạn 1 – Thu Nhận Dữ Liệu (Input)

Camera hoặc file video là nguồn dữ liệu đầu vào. Từng frame được đọc liên tục theo thời gian thực thông qua OpenCV. Hệ thống hỗ trợ hai trường hợp:

- **Webcam thực tế** (`CAMERA_SOURCE = 0`): đọc trực tiếp từ thiết bị phần cứng, dùng backend `cv.CAP_DSHOW` trên Windows để ổn định hơn.
- **File video** (ví dụ `test.mp4` hoặc `2.mp4`): dùng để kiểm thử, tự động tua lại khi hết (`CAP_PROP_POS_FRAMES = 0`).

Nếu mất kết nối hoặc không đọc được frame, hệ thống không dừng mà `time.sleep(0.05)` rồi thử lại ở frame tiếp theo, đảm bảo giám sát liên tục không bị gián đoạn.

Sau khi mở nguồn video thành công, hệ thống cấu hình độ phân giải chuẩn `640×480` và FPS mong muốn là **30 FPS** để đồng bộ với tốc độ xử lý.

**Code trọng tâm – `main.py` (Bước 1):**

```python
# config.py: CAMERA_SOURCE = 0 (webcam) hoặc "test.mp4" (file video)
if isinstance(CAMERA_SOURCE, str):
    cap = cv.VideoCapture(CAMERA_SOURCE)                # Nguồn: file video
else:
    cap = cv.VideoCapture(CAMERA_SOURCE, cv.CAP_DSHOW)  # Nguồn: webcam (Windows)

# Cấu hình độ phân giải và FPS mặc định
cap.set(cv.CAP_PROP_FRAME_WIDTH,  FRAME_W)  # 640px
cap.set(cv.CAP_PROP_FRAME_HEIGHT, FRAME_H)  # 480px
cap.set(cv.CAP_PROP_FPS, 30)

# Vòng lặp chính: đọc liên tục từng frame
ok, frame = cap.read()
if not ok:
    if isinstance(CAMERA_SOURCE, str):  # Hết video → tua lại từ đầu
        cap.set(cv.CAP_PROP_POS_FRAMES, 0)
    else:                               # Mất tín hiệu → chờ và thử lại
        time.sleep(0.05)
    continue
```

---

## Giai Đoạn 2 – Tiền Xử Lý (Preprocessing)

Trước khi đưa frame vào mô hình AI, hệ thống thực hiện bước tiền xử lý nhằm chuẩn hóa dữ liệu và bảo toàn frame gốc.

Khi gọi `model.track(frame, ...)`, thư viện **Ultralytics** tự động thực hiện pipeline chuẩn hóa nội bộ:
- **Resize / Scale**: đưa frame về `640×640` phù hợp với YOLOv8.
- **Normalize**: chuẩn hóa giá trị pixel từ `[0–255]` về `[0.0–1.0]`.
- **Padding (letterbox)**: giữ tỉ lệ khung hình, bổ sung vùng đệm nếu cần.

Hệ thống áp dụng kỹ thuật **frame skipping** (`frame_count % 2 == 1`): chỉ chạy model AI trên frame lẻ. Các frame chẵn tái sử dụng kết quả `last_boxes`, `last_ids`, `last_confs` từ frame trước, giúp giảm tải CPU/GPU trên máy tính cấu hình thấp.

Frame được sao chép (`frame.copy()`) để bảo toàn dữ liệu gốc; mọi annotation (khung bbox, nhãn, chấm tâm) đều được vẽ lên bản sao `disp_frame`.

**Code trọng tâm – `main.py` (Bước 2):**

```python
# Bảo toàn frame gốc cho model, chỉ vẽ lên bản sao
disp_frame = frame.copy()

# Bộ đệm kết quả của frame trước (dùng khi frame skipping)
last_boxes = []   # Tọa độ bounding box
last_ids   = []   # Track ID
last_confs = []   # Độ tin cậy
```

---

## Giai Đoạn 3 – Phát Hiện và Theo Dõi Đối Tượng (Detection & Tracking)

Hệ thống sử dụng mô hình **YOLOv8n** (`yolov8n.pt`) để phát hiện người trong từng frame. Kết quả trả về gồm:

| Thông tin | Kiểu dữ liệu | Mô tả |
|-----------|-------------|-------|
| **Bounding Box** | `float[4]` – `[x1, y1, x2, y2]` | Tọa độ hình chữ nhật bao quanh đối tượng |
| **Confidence** | `float` – `[0.0–1.0]` | Độ tin cậy phát hiện, ngưỡng `conf=0.4` |
| **Track ID** | `int` | Mã định danh duy nhất, duy trì ổn định qua nhiều frame |

Sử dụng **Tracking** (không chỉ Detect) mang lại hai lợi ích:
1. **Tránh đếm lặp**: cùng một người chỉ có một Track ID duy nhất.
2. **Đo thời gian chính xác**: biết được đối tượng đã đứng trong vùng cấm bao nhiêu giây dựa trên ID đó.

Model được bảo vệ bằng `threading.Lock()` để tránh race condition khi đa luồng (SSE + video stream chạy song song). Chỉ nhận diện class `"person"` (lọc qua `PERSON_CLS`).

**Code trọng tâm – `main.py` (Bước 3 & 4):**

```python
# Frame skipping: chỉ chạy model AI trên frame lẻ
if frame_count % 2 == 1 or len(last_boxes) == 0:
    with model_lock:  # Thread-safe: tránh race condition khi đa luồng
        results = model.track(
            frame,
            persist=True,       # Giữ track_id ổn định qua nhiều frame
            verbose=False,
            classes=PERSON_CLS, # Chỉ nhận diện class "person"
            conf=0.4            # Bỏ qua phát hiện có độ tin cậy < 40%
        )

# Trích xuất kết quả phát hiện + tracking
if results[0].boxes is not None and results[0].boxes.id is not None:
    last_boxes = results[0].boxes.xyxy.cpu().numpy()       # Tọa độ [x1, y1, x2, y2]
    last_ids   = results[0].boxes.id.int().cpu().tolist()  # Track ID duy nhất
    last_confs = results[0].boxes.conf.cpu().numpy()       # Độ tin cậy
else:
    last_boxes, last_ids, last_confs = [], [], []
```

---

## Giai Đoạn 4 – Phân Tích Vùng Cấm (ROI Processing)

Hệ thống kiểm tra xem đối tượng có đang đứng trong vùng cấm (**Region of Interest – ROI**) hay không. Vùng cấm do người dùng tự vẽ trên giao diện web dưới dạng **đa giác (polygon)** và được lưu vào `zone.json` thông qua API `POST /api/zone` trong `router.py`.

**Bước quy đổi tọa độ (Scale):** Tọa độ vùng cấm được lưu theo độ phân giải chuẩn `640×480`. Hệ thống tính tỉ lệ `sx = sw / FRAME_W` và `sy = sh / FRAME_H` để quy đổi sang kích thước thực tế của frame từ camera.

**Điểm đại diện:** Tâm (center) của Bounding Box được dùng làm điểm đại diện vị trí đối tượng:

$$c_x = \frac{x_1 + x_2}{2}, \quad c_y = \frac{y_1 + y_2}{2}$$

**Thuật toán Point-in-Polygon Test** (`cv.pointPolygonTest`):
- Kết quả `≥ 0` → điểm nằm **TRONG hoặc TRÊN cạnh** của đa giác → **Xâm nhập**.
- Kết quả `< 0` → điểm nằm **NGOÀI** đa giác → **An toàn**.

Màu sắc bounding box thay đổi theo trạng thái: **đỏ** `(0, 0, 255)` khi xâm nhập, **xanh** `(0, 255, 0)` khi an toàn.

**Code trọng tâm – `main.py` (Bước 5):**

```python
# Bước 1: Scale tọa độ vùng cấm về đúng kích thước frame thực
sh, sw = frame.shape[:2]
sx, sy = sw / FRAME_W, sh / FRAME_H
scaled_zone = np.array(
    [[int(p[0] * sx), int(p[1] * sy)] for p in router.zone_points],
    dtype=np.int32,
)
has_zone = len(scaled_zone) >= 3  # Cần ít nhất 3 điểm để tạo polygon

# Bước 2: Duyệt từng đối tượng, tính tâm Bounding Box
for box, tid, conf in zip(last_boxes, last_ids, last_confs):
    x1, y1, x2, y2 = map(int, box)
    cx = (x1 + x2) // 2  # Tọa độ X tâm
    cy = (y1 + y2) // 2  # Tọa độ Y tâm

    # Bước 3: Kiểm tra tâm có nằm trong polygon vùng cấm không
    is_inside = False
    if has_zone:
        is_inside = cv.pointPolygonTest(
            scaled_zone,
            (float(cx), float(cy)),
            False    # False = chỉ trả về dấu (+/-), không tính khoảng cách
        ) >= 0

    # Đổi màu theo trạng thái
    color = (0, 0, 255) if is_inside else (0, 255, 0)  # Đỏ : Xanh
    cv.rectangle(disp_frame, (x1, y1), (x2, y2), color, 2)
    cv.circle(disp_frame, (cx, cy), 5, color, -1)
    cv.putText(disp_frame, f"ID:{tid}", (x1, max(20, y1 - 8)),
               cv.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
```

---

## Giai Đoạn 5 – Xử Lý Logic Xâm Nhập (Decision Making)

Hệ thống không đưa ra cảnh báo ngay lập tức mà áp dụng **hai điều kiện thời gian** để tăng độ chính xác và tránh cảnh báo sai:

| Tham số | Giá trị mặc định | Vai trò |
|---------|-----------------|---------|
| `ZONE_HOLD_SECS` | `3.0 giây` | Đứng trong zone đủ thời gian này mới tính là xâm nhập |
| `ZONE_COOLDOWN` | `5 giây` | Chờ đủ thời gian này giữa hai lần cảnh báo cùng track_id |
| `ZONE_MISS_TOLERANCE` | `15 frame` | Số frame vắng mặt tối đa trước khi reset trạng thái zone |

**Cơ chế `zone_missed`**: Hệ thống không reset ngay khi đối tượng tạm biến mất khỏi zone (do bị che khuất, nhiễu tracking). Chỉ khi vắng mặt liên tục `> 15 frame` thì mới xóa bộ đếm thời gian (`zone_enter_times`). Điều này tránh reset sai khi đối tượng thực sự vẫn đứng đó.

**Luồng quyết định:**

```
Đối tượng vào zone (is_inside = True)
    │
    ├── [Lần đầu] → lưu zone_enter_times[tid] = now
    │
    ├── time_in_zone = now - zone_enter_times[tid]
    │
    ├── time_in_zone >= hold_secs (3s)?
    │       VÀ (now - last_alert[tid]) >= cooldown (5s)?
    │           │
    │           └─► GỬI CẢNH BÁO → zone_last_alert[tid] = now
    │                               Lưu ảnh hiện trường
    │                               dispatch_alert()
    └── Chưa đủ điều kiện → bỏ qua, frame tiếp theo tiếp tục kiểm tra

Đối tượng ngoài zone (is_inside = False)
    ├── zone_missed[tid] += 1
    └── zone_missed[tid] > 15 → xóa zone_enter_times[tid]
```

**Code trọng tâm – `main.py` (Bước 6, 7 & 8):**

```python
if is_inside:
    anyone_inside = True
    state["zone_missed"][tid] = 0          # Đang trong zone → reset missed counter

    # Ghi nhận thời điểm lần đầu bước vào vùng cấm
    if tid not in state["zone_enter_times"]:
        state["zone_enter_times"][tid] = now

    time_in_zone  = now - state["zone_enter_times"][tid]
    hold_secs     = state["zone_hold_secs"]
    cooldown_secs = state["zone_cooldown"]
    last_tid_alert = state["zone_last_alert"].get(tid, 0)

    # Điều kiện kép: đủ thời gian lưu trú VÀ hết cooldown
    if (time_in_zone >= hold_secs) and (now - last_tid_alert >= cooldown_secs):
        state["zone_last_alert"][tid] = now  # Đánh dấu đã báo động

        # Ghi bằng chứng ảnh hiện trường
        img_filename = f"zone_{tid}_{int(now)}.jpg"
        img_path = os.path.join(OUTPUT_DIR, img_filename)
        cv.imwrite(img_path, disp_frame.copy())

        print(f"[{time.strftime('%H:%M:%S')}] BÁO ĐỘNG | ID={tid} | {time_in_zone:.1f}s")
        dispatch_alert(img_path, tid, is_intrusion=True)
else:
    # Tăng đếm frame vắng mặt
    state["zone_missed"][tid] = state["zone_missed"].get(tid, 0) + 1
    if state["zone_missed"][tid] > ZONE_MISS_TOLERANCE:   # > 15 frame
        state["zone_enter_times"].pop(tid, None)
        state["zone_alerted"].discard(tid)
```

---

## Giai Đoạn 6 – Gửi Cảnh Báo (Output & Alert)

Khi xác định có hành vi xâm nhập, hệ thống đồng thời thực hiện **ba hành động song song**:

1. **Lưu ảnh hiện trường** vào thư mục `alerts/` với tên `zone_{tid}_{timestamp}.jpg`, kèm annotation (khung đỏ, chấm tâm, nhãn ID).
2. **Gửi cảnh báo Telegram** kèm ảnh và thông tin chi tiết qua `telegram_utils.send_formatted_intrusion_alert()`.
3. **Cập nhật Web Dashboard** theo thời gian thực qua **Server-Sent Events (SSE)** tại endpoint `GET /api/alerts`.

Quá trình gửi Telegram được xử lý trong **thread riêng** (`threading.Thread(daemon=True)`), đảm bảo hệ thống không bị treo trong khi chờ phản hồi từ mạng (timeout = 15 giây). Video stream MJPEG được phục vụ qua endpoint `GET /api/stream`, trả về từng frame dưới định dạng `multipart/x-mixed-replace`.

**Code trọng tâm – `telegram_utils.py`:**

```python
def send_formatted_intrusion_alert(photo_path, token, chat_id, track_id, is_intrusion, hold_secs):
    timestamp = time.strftime("%H:%M:%S %d/%m/%Y")
    title     = "🚨 CẢNH BÁO XÂM NHẬP 🚨" if is_intrusion else "🚨 PHÁT HIỆN NGƯỜI 🚨"
    caption   = (
        f"{title}\n"
        f"{'─' * 30}\n"
        f"👤 Đối tượng: #{track_id}\n"
        f"⏱ Thời gian: {timestamp}"
    )
    # POST https://api.telegram.org/bot{token}/sendPhoto
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(photo_path, "rb") as f:
        res = requests.post(url, files={"photo": f},
                            data={"chat_id": chat_id, "caption": caption}, timeout=15)
    return True
```

**Code trọng tâm – `main.py` (Bước 9 – gửi không đồng bộ):**

```python
def dispatch_alert(img_path: str, track_id: int, is_intrusion: bool = False):
    """Gửi cảnh báo trong thread riêng, không làm chậm luồng video chính."""
    def _run():
        telegram_utils.send_formatted_intrusion_alert(...)  # Gửi Telegram

        # Gửi SSE cho trình duyệt (cập nhật dashboard real-time)
        payload = json.dumps({
            "id": track_id, "time": f"{date_str} {time_str}",
            "msg": msg, "intrusion": is_intrusion,
            "img_url": f"/alerts/{os.path.basename(img_path)}",
        })
        loop.create_task(_broadcast(payload))  # Broadcast tới tất cả SSE client

    threading.Thread(target=_run, daemon=True).start()  # Chạy tách biệt

# Bước 9: Encode và stream frame video
_, buf = cv.imencode(".jpg", disp_frame, [cv.IMWRITE_JPEG_QUALITY, 85])
yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"

# Cập nhật trạng thái SSE (số người + có xâm nhập không)
dispatch_status(len(active_ids), anyone_inside)
```

---

## Tổng Kết Các Tham Số Cấu Hình

| Tham số | File | Giá trị mặc định | Mô tả |
|---------|------|-----------------|-------|
| `CAMERA_SOURCE` | `config.py` | `0` (webcam) | Nguồn video đầu vào |
| `MODEL_PATH` | `config.py` | `yolov8n.pt` | Đường dẫn model YOLOv8 |
| `ZONE_HOLD_SECS` | `config.py` | `3.0 s` | Thời gian tối thiểu trong zone để báo động |
| `ZONE_COOLDOWN` | `config.py` | `5 s` | Khoảng cách tối thiểu giữa hai cảnh báo |
| `FRAME_W / FRAME_H` | `main.py` | `640 / 480` | Độ phân giải chuẩn của hệ thống |
| `ZONE_MISS_TOLERANCE` | `main.py` | `15 frame` | Số frame vắng mặt trước khi reset zone |
| `conf=0.4` | `main.py` | `0.4` | Ngưỡng tin cậy tối thiểu của YOLO |
| `frame_count % 2` | `main.py` | — | Chỉ chạy AI trên frame lẻ (frame skipping) |
| `JPEG_QUALITY` | `main.py` | `85` | Chất lượng encode ảnh stream |

> **Lưu ý:** Các tham số `zone_hold_secs`, `zone_cooldown`, `telegram_token` và `telegram_chat_id` có thể được điều chỉnh trực tiếp qua giao diện web (API `POST /api/config`) mà không cần khởi động lại hệ thống, nhờ cơ chế **shared state** lưu vào `settings.json`.
