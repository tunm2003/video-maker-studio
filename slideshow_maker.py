"""
Core video generation logic - Python version of make_slideshow.ps1
Calls FFmpeg via subprocess.
"""
import subprocess
import json
import math
from pathlib import Path


def _run(args: list, capture: bool = True):
    """Run a command and return CompletedProcess."""
    return subprocess.run(args + ['-y'], capture_output=capture)


def probe_video(path: Path) -> tuple[float, int, int]:
    """Return (duration_sec, width, height) of a video file."""
    r = subprocess.run([
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', str(path)
    ], capture_output=True, text=True)
    info = json.loads(r.stdout)
    duration = float(info['format']['duration'])
    vs = next(s for s in info['streams'] if s['codec_type'] == 'video')
    return duration, int(vs['width']), int(vs['height'])


def _build_slideshow_filter(n: int, slide_dur: float, cf: float,
                             transition: str, w: int, h: int) -> str:
    """Build FFmpeg filter_complex string for a slideshow."""
    scales = ''.join(
        f'[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,'
        f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1[s{i}];'
        for i in range(n)
    )
    if n == 1 or transition == 'cut':
        labels = ''.join(f'[s{i}]' for i in range(n))
        chain = f'{labels}concat=n={n}:v=1:a=0[vout]'
    else:
        chain, prev = '', '[s0]'
        for i in range(1, n):
            offset = round(i * (slide_dur - cf), 3)
            lbl = '[vout]' if i == n - 1 else f'[x{i}]'
            chain += f'{prev}[s{i}]xfade=transition={transition}:duration={cf}:offset={offset}{lbl};'
            prev = f'[x{i}]'
    return scales + chain.rstrip(';')


def make_slideshow_clip(images: list[Path], slide_dur: float, cf: float,
                        transition: str, w: int, h: int, out: Path):
    """Render a silent slideshow clip from a list of image paths."""
    args = []
    for img in images:
        args += ['-loop', '1', '-t', str(slide_dur), '-i', str(img)]
    fc = _build_slideshow_filter(len(images), slide_dur, cf, transition, w, h)
    args += ['-filter_complex', fc, '-map', '[vout]',
             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'fast', str(out)]
    _run(['ffmpeg'] + args)


def make_video(images: list[Path], ref_video: Path,
               intro_duration: float, tutorial_start: float, tutorial_end: float,
               transition: str, output_path: Path,
               progress=None) -> Path:
    """
    Generate the final slideshow video.
    progress: callable(fraction: float, message: str) | None
    """
    def prog(f, msg):
        if progress:
            progress(f, msg)

    tmp = output_path.parent

    # ── Probe ──────────────────────────────────────────────────────────────────
    total_dur, w, h = probe_video(ref_video)
    prog(0.05, f"Video ref: {w}×{h}, {total_dur:.1f}s")

    has_tutorial = (tutorial_end > tutorial_start >= 0) and (tutorial_end <= total_dur)
    if tutorial_end > tutorial_start > 0 and tutorial_end > total_dur:
        prog(0.05, "⚠️ Tutorial end vượt quá độ dài video → bỏ qua tutorial")
    tut_len = round(tutorial_end - tutorial_start, 3) if has_tutorial else 0.0
    has_intro = 0 < intro_duration <= total_dur
    cf = 0.0 if transition == 'cut' else 0.5
    n = len(images)

    # ── Extract audio ──────────────────────────────────────────────────────────
    audio = tmp / 'audio.aac'
    _run(['ffmpeg', '-i', str(ref_video), '-vn', '-acodec', 'aac', '-b:a', '192k', str(audio)])
    prog(0.15, "Đã trích nhạc...")

    # ── Mode: Tutorial embedded ────────────────────────────────────────────────
    if has_tutorial:
        intro_end = intro_duration if has_intro else 0.0
        sec_before = max(0.0, tutorial_start - intro_end)
        sec_after  = max(0.0, total_dur - tutorial_end)
        total_slide = sec_before + sec_after
        if total_slide <= 0:
            raise ValueError("Tutorial chiếm hết video, không còn chỗ cho ảnh")

        if sec_before <= 0:
            n1, n2 = 0, n
        elif sec_after <= 0:
            n1, n2 = n, 0
        else:
            n1 = max(1, min(n - 1, round(n * sec_before / total_slide)))
            n2 = n - n1

        cf1 = 0.0 if (n1 <= 1 or transition == 'cut') else cf
        cf2 = 0.0 if (n2 <= 1 or transition == 'cut') else cf
        sd1 = round((sec_before + (n1 - 1) * cf1) / n1, 3) if n1 else 0.0
        sd2 = round((sec_after  + (n2 - 1) * cf2) / n2, 3) if n2 else 0.0

        clip_list = []

        if has_intro:
            intro_f = tmp / 'intro_clip.mp4'
            _run(['ffmpeg', '-t', str(intro_duration), '-i', str(ref_video),
                  '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'fast', str(intro_f)])
            clip_list.append(intro_f)
            prog(0.25, "Đã cắt intro...")

        if n1 > 0:
            s1 = tmp / 'slideshow1.mp4'
            make_slideshow_clip(images[:n1], sd1, cf1, transition, w, h, s1)
            clip_list.append(s1)
            prog(0.45, f"Đã tạo slideshow trước tutorial ({n1} ảnh)...")

        tut_f = tmp / 'tutorial_clip.mp4'
        _run(['ffmpeg', '-ss', str(tutorial_start), '-t', str(tut_len),
              '-i', str(ref_video), '-an', '-c:v', 'libx264',
              '-pix_fmt', 'yuv420p', '-preset', 'fast', str(tut_f)])
        clip_list.append(tut_f)
        prog(0.60, "Đã cắt tutorial...")

        if n2 > 0:
            s2 = tmp / 'slideshow2.mp4'
            make_slideshow_clip(images[n1:], sd2, cf2, transition, w, h, s2)
            clip_list.append(s2)
            prog(0.75, f"Đã tạo slideshow sau tutorial ({n2} ảnh)...")

        # Concat
        combined = tmp / 'combined_v.mp4'
        nc = len(clip_list)
        ci = sum([['-i', str(c)] for c in clip_list], [])
        cf_str = ''.join(f'[{i}:v]' for i in range(nc)) + f'concat=n={nc}:v=1:a=0[outv]'
        _run(['ffmpeg'] + ci + ['-filter_complex', cf_str, '-map', '[outv]',
              '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'fast', str(combined)])
        prog(0.85, "Đã ghép video...")

        _run(['ffmpeg', '-i', str(combined), '-i', str(audio),
              '-c:v', 'copy', '-c:a', 'aac', '-shortest', str(output_path)])

    # ── Mode: Intro only ───────────────────────────────────────────────────────
    elif has_intro:
        min_slide   = 2.0 if n >= 10 else 3.0
        bgm_avail   = max(0.1, total_dur - intro_duration)
        needed      = round((bgm_avail + (n - 1) * cf) / n, 3)
        slide_dur   = max(min_slide, needed)

        intro_f = tmp / 'intro_clip.mp4'
        _run(['ffmpeg', '-t', str(intro_duration), '-i', str(ref_video),
              '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'fast', str(intro_f)])
        prog(0.30, "Đã cắt intro...")

        ss_f = tmp / 'slideshow_v.mp4'
        make_slideshow_clip(images, slide_dur, cf, transition, w, h, ss_f)
        prog(0.65, "Đã tạo slideshow...")

        combined = tmp / 'combined_v.mp4'
        _run(['ffmpeg', '-i', str(intro_f), '-i', str(ss_f),
              '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[outv]',
              '-map', '[outv]', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
              '-preset', 'fast', str(combined)])
        prog(0.80, "Đã ghép...")

        _run(['ffmpeg', '-i', str(combined), '-i', str(audio),
              '-c:v', 'copy', '-c:a', 'aac', '-shortest', str(output_path)])

    # ── Mode: Pure slideshow ───────────────────────────────────────────────────
    else:
        min_slide = 2.0 if n >= 10 else 3.0
        needed    = round((total_dur + (n - 1) * cf) / n, 3)
        slide_dur = max(min_slide, needed)
        total_out = round(n * slide_dur - (n - 1) * cf, 2)
        loop_audio = (total_out < total_dur) and (needed < min_slide)

        args = []
        for img in images:
            args += ['-loop', '1', '-t', str(slide_dur), '-i', str(img)]
        if loop_audio:
            args += ['-stream_loop', '-1']
        args += ['-i', str(audio)]

        fc = _build_slideshow_filter(n, slide_dur, cf, transition, w, h)
        audio_idx = n
        args += ['-filter_complex', fc, '-map', '[vout]', '-map', f'{audio_idx}:a',
                 '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p',
                 '-shortest', str(output_path)]
        prog(0.30, "Đang tạo video...")
        _run(['ffmpeg'] + args)

    prog(1.0, "✅ Hoàn thành!")
    return output_path
