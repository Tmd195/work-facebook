# Work Facebook – Auto content Forex

Hệ thống tự viết bài và thiết kế ảnh cho Facebook Page về forex/vàng (XAUUSD, EURUSD, GBPUSD, DXY).

## Cài đặt

```bash
pip install -r requirements.txt
copy .env.example .env      # rồi điền ANTHROPIC_API_KEY, TWELVEDATA_API_KEY
```

## Chạy thử

```bash
python run.py morning
```

Kết quả nằm ở `output/<ngày>/`:
- `morning.png` – banner 1080x1350
- `morning.txt` – nội dung bài đăng
- `morning.json` – dữ liệu gốc + bài AI (để đối chiếu)

Hiện hệ thống **chưa đăng lên Facebook**, chỉ tạo bài để duyệt.

## Luồng xử lý bài buổi sáng

1. `src/data/prices.py` – lấy nến D1 (Twelve Data → dự phòng Yahoo; vàng spot từ gold-api)
2. `src/analysis.py` – tính pivot, EMA20/50, RSI, ATR, hỗ trợ/kháng cự
3. `src/data/calendar.py` – lịch kinh tế ForexFactory, lọc USD/EUR/GBP, đổi sang giờ VN
4. `src/content/morning.py` – Claude Opus 5 viết bài, **kiểm tra mọi con số khớp dữ liệu**;
   sai thì cho viết lại 1 lần, vẫn sai thì dùng bản template
5. `src/design/morning_banner.py` – vẽ banner (màu/font ở `src/design/theme.py`)

Đổi tên page, mã theo dõi, giờ đăng trong `config.yaml`.
