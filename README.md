# 🎬 Video Maker Studio

Tạo video slideshow tự động từ ảnh + nhạc nền, hỗ trợ Intro và Tutorial.

## Tính năng

- **Thư viện Video Ref** — lưu nhiều video ref, chọn lại bất cứ lúc nào
- **Upload ảnh** — thứ tự chọn file = thứ tự xuất hiện trong video
- **Intro** — giữ nguyên đoạn đầu video ref
- **Tutorial** — giữ nguyên đoạn tutorial, ảnh tự động điền xung quanh
- **15 hiệu ứng chuyển cảnh** — cut, smoothleft, fade, dissolve, zoomin...

## Cấu trúc video

```
[Intro] → [Slideshow 1] → [Tutorial] → [Slideshow 2]
```

## Deploy

1. Push repo lên GitHub
2. Vào [share.streamlit.io](https://share.streamlit.io)
3. Kết nối repo → Deploy

## Chạy local

```bash
pip install streamlit
streamlit run app.py
```

> FFmpeg phải được cài sẵn trên máy.
