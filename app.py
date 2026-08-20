import streamlit as st
import tempfile
from pathlib import Path
import slideshow_maker

# ── Config ─────────────────────────────────────────────────────────────────────
VIDEO_REFS_DIR = Path("video_refs")
VIDEO_REFS_DIR.mkdir(exist_ok=True)

TRANSITIONS = [
    ("cut",         "cut — cắt thẳng (theo video ref)"),
    ("smoothleft",  "smoothleft — trượt mượt"),
    ("fade",        "fade — mờ dần"),
    ("fadewhite",   "fadewhite — mờ qua trắng"),
    ("fadeblack",   "fadeblack — mờ qua đen"),
    ("dissolve",    "dissolve — hòa tan"),
    ("zoomin",      "zoomin — zoom phóng to"),
    ("slideleft",   "slideleft — trượt trái"),
    ("slideright",  "slideright — trượt phải"),
    ("slideup",     "slideup — trượt lên"),
    ("wipeleft",    "wipeleft — gạt trái"),
    ("wipeup",      "wipeup — gạt lên"),
    ("pixelize",    "pixelize — vỡ pixel"),
    ("hblur",       "hblur — mờ ngang"),
    ("circleopen",  "circleopen — mở tròn"),
]
TRANS_KEYS   = [t[0] for t in TRANSITIONS]
TRANS_LABELS = [t[1] for t in TRANSITIONS]

# ── Page setup ─────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Video Maker Studio", page_icon="🎬", layout="wide")

st.markdown("""
<style>
  .block-container { padding-top: 2rem; }
  .stButton > button { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

st.title("🎬 Video Maker Studio")
st.caption("Tạo video slideshow từ ảnh + nhạc nền tự động · Powered by FFmpeg")

tab_create, tab_refs = st.tabs(["✨ Tạo Video", "📚 Thư viện Video Ref"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: TẠO VIDEO
# ══════════════════════════════════════════════════════════════════════════════
with tab_create:
    col_left, col_right = st.columns([1, 1], gap="large")

    # ── Left column: inputs ───────────────────────────────────────────────────
    with col_left:
        # 1. Images
        st.subheader("1. Ảnh")
        uploaded_images = st.file_uploader(
            "Upload ảnh — thứ tự chọn file = thứ tự xuất hiện trong video",
            type=["jpg", "jpeg", "png", "webp", "bmp"],
            accept_multiple_files=True,
            key="img_uploader"
        )
        if uploaded_images:
            st.caption(f"✅ {len(uploaded_images)} ảnh đã chọn")
            preview_cols = st.columns(min(len(uploaded_images), 5))
            for i, img in enumerate(uploaded_images[:5]):
                preview_cols[i].image(img, caption=f"#{i+1}", use_container_width=True)
            if len(uploaded_images) > 5:
                st.caption(f"... và {len(uploaded_images) - 5} ảnh nữa")

        st.divider()

        # 2. Video Ref
        st.subheader("2. Video Ref (nhạc nền)")
        refs = sorted(VIDEO_REFS_DIR.glob("*.mp4"))
        ref_names = [r.name for r in refs]

        ref_source = st.radio("Nguồn video ref", ["Từ thư viện", "Upload mới"],
                              horizontal=True, label_visibility="collapsed")

        selected_ref_path = None

        if ref_source == "Từ thư viện":
            if not ref_names:
                st.info("Chưa có ref nào. Upload ở tab **Thư viện Video Ref** trước.")
            else:
                chosen = st.selectbox("Chọn video ref", ref_names)
                selected_ref_path = VIDEO_REFS_DIR / chosen
                size_mb = selected_ref_path.stat().st_size / 1024 / 1024
                dur, w, h = slideshow_maker.probe_video(selected_ref_path)
                st.caption(f"📐 {w}×{h} · ⏱ {dur:.1f}s · 💾 {size_mb:.1f} MB")
        else:
            new_ref = st.file_uploader("Upload file .mp4", type=["mp4"], key="ref_upload_create")
            if new_ref:
                save_col1, save_col2 = st.columns([3, 1])
                with save_col1:
                    st.caption(f"📎 {new_ref.name} ({new_ref.size / 1024 / 1024:.1f} MB)")
                with save_col2:
                    if st.button("💾 Lưu vào thư viện"):
                        (VIDEO_REFS_DIR / new_ref.name).write_bytes(new_ref.getbuffer())
                        st.success("Đã lưu!")
                        st.rerun()
                # Store temporarily for this session
                if 'temp_ref_bytes' not in st.session_state or st.session_state.get('temp_ref_name') != new_ref.name:
                    st.session_state['temp_ref_bytes'] = new_ref.getbuffer()
                    st.session_state['temp_ref_name'] = new_ref.name
                selected_ref_path = "__session__"

    # ── Right column: settings ────────────────────────────────────────────────
    with col_right:
        st.subheader("3. Cài đặt")

        intro_duration = st.number_input(
            "⏩ Intro từ video ref (giây · 0 = tắt)",
            min_value=0.0, value=0.0, step=0.5, format="%.1f"
        )

        st.markdown("**🎓 Tutorial** — giữ nguyên đoạn từ video ref")
        tc1, tc2 = st.columns(2)
        with tc1:
            tutorial_start = st.number_input("Bắt đầu (giây)", min_value=0.0,
                                              value=0.0, step=0.5, format="%.2f")
        with tc2:
            tutorial_end = st.number_input("Kết thúc (giây)", min_value=0.0,
                                            value=0.0, step=0.5, format="%.2f")

        if tutorial_end > tutorial_start > 0:
            st.caption(f"📐 Cấu trúc: `[Intro] → [Slideshow] → [Tutorial {tutorial_start:.1f}s–{tutorial_end:.1f}s] → [Slideshow]`")

        st.markdown("**🎞 Kiểu chuyển cảnh**")
        trans_idx = st.selectbox("Transition", range(len(TRANSITIONS)),
                                  format_func=lambda i: TRANS_LABELS[i])
        transition = TRANS_KEYS[trans_idx]

        st.divider()

        # Generate button
        ready = bool(uploaded_images) and selected_ref_path is not None
        generate = st.button("🎬 Tạo Video", type="primary",
                              use_container_width=True, disabled=not ready)

        if not uploaded_images:
            st.caption("⬅️ Chưa chọn ảnh")
        if selected_ref_path is None:
            st.caption("⬅️ Chưa chọn video ref")

    # ── Generate ──────────────────────────────────────────────────────────────
    if generate and ready:
        st.divider()
        prog_bar  = st.progress(0.0)
        prog_text = st.empty()

        def on_progress(frac: float, msg: str):
            prog_bar.progress(min(frac, 1.0))
            prog_text.markdown(f"⏳ {msg}")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Save images in upload order
            img_paths = []
            for i, f in enumerate(uploaded_images):
                p = tmp_path / f"{i:04d}_{f.name}"
                p.write_bytes(f.getbuffer())
                img_paths.append(p)

            # Resolve ref path
            if selected_ref_path == "__session__":
                ref_p = tmp_path / st.session_state['temp_ref_name']
                ref_p.write_bytes(st.session_state['temp_ref_bytes'])
            else:
                ref_p = selected_ref_path

            out_p = tmp_path / "output.mp4"

            try:
                slideshow_maker.make_video(
                    images=img_paths,
                    ref_video=ref_p,
                    intro_duration=intro_duration,
                    tutorial_start=tutorial_start,
                    tutorial_end=tutorial_end,
                    transition=transition,
                    output_path=out_p,
                    progress=on_progress,
                )

                if out_p.exists() and out_p.stat().st_size > 0:
                    prog_bar.progress(1.0)
                    prog_text.markdown("✅ **Hoàn thành!**")
                    video_bytes = out_p.read_bytes()
                    size_mb = len(video_bytes) / 1024 / 1024

                    res_col1, res_col2 = st.columns([2, 1])
                    with res_col1:
                        st.video(video_bytes)
                    with res_col2:
                        st.metric("Dung lượng", f"{size_mb:.1f} MB")
                        st.metric("Số ảnh", len(uploaded_images))
                        st.download_button(
                            "⬇️ Tải video về",
                            data=video_bytes,
                            file_name="slideshow.mp4",
                            mime="video/mp4",
                            use_container_width=True,
                        )
                else:
                    prog_bar.empty()
                    st.error("❌ Tạo video thất bại. Kiểm tra lại file ảnh và video ref.")

            except Exception as e:
                prog_bar.empty()
                st.error(f"❌ Lỗi: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: THƯ VIỆN VIDEO REF
# ══════════════════════════════════════════════════════════════════════════════
with tab_refs:
    st.subheader("📚 Thư viện Video Ref")

    # Upload new
    with st.expander("➕ Thêm video ref mới", expanded=not refs):
        new_ref_lib = st.file_uploader("Upload file .mp4", type=["mp4"], key="ref_upload_lib")
        if new_ref_lib:
            dest = VIDEO_REFS_DIR / new_ref_lib.name
            dest.write_bytes(new_ref_lib.getbuffer())
            st.success(f"✅ Đã lưu **{new_ref_lib.name}** vào thư viện!")
            st.rerun()

    st.divider()

    refs = sorted(VIDEO_REFS_DIR.glob("*.mp4"))
    if not refs:
        st.info("Chưa có video ref nào. Upload ở trên để thêm vào thư viện.")
    else:
        for ref in refs:
            with st.container():
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                size_mb = ref.stat().st_size / 1024 / 1024
                try:
                    dur, w, h = slideshow_maker.probe_video(ref)
                    meta = f"{w}×{h} · {dur:.1f}s · {size_mb:.1f} MB"
                except Exception:
                    meta = f"{size_mb:.1f} MB"
                c1.markdown(f"🎵 **{ref.name}**  \n`{meta}`")

                if c2.button("▶️ Preview", key=f"prev_{ref.name}"):
                    st.session_state[f"show_{ref.name}"] = not st.session_state.get(f"show_{ref.name}", False)

                c3.download_button("⬇️", data=ref.read_bytes(),
                                   file_name=ref.name, mime="video/mp4",
                                   key=f"dl_{ref.name}")

                if c4.button("🗑️ Xóa", key=f"del_{ref.name}"):
                    ref.unlink()
                    st.rerun()

                if st.session_state.get(f"show_{ref.name}", False):
                    st.video(str(ref))

                st.divider()
