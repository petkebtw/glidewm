"""File conversion engine: images (ffmpeg / ImageMagick / PIL), video + audio (ffmpeg), archives (7z/tar)."""
import os, re, shutil, subprocess, tempfile

IMG = {"png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff", "ico", "avif", "heic", "heif", "svg", "jxl", "pdf"}
VID = {"mp4", "mkv", "webm", "mov", "avi", "flv", "m4v", "wmv", "mpg", "mpeg", "ts", "3gp", "ogv"}
AUD = {"mp3", "wav", "flac", "ogg", "opus", "m4a", "aac", "wma", "aiff", "oga"}
ARC = {"zip", "7z", "tar", "gz", "tgz", "xz", "bz2", "rar", "zst", "txz"}
TARGETS = {
    "image": ["png", "jpg", "webp", "avif", "gif", "bmp", "tiff", "ico", "pdf", "mp4"],
    "video": ["mp4", "mkv", "webm", "mov", "avi", "gif", "mp3", "flac", "wav", "ogg", "opus", "m4a"],
    "audio": ["mp3", "wav", "flac", "ogg", "opus", "m4a", "aac"],
    "archive": ["zip", "7z", "tar", "tar.gz", "tar.xz"],
}


_ENC = None
NEED = {"mp3": "libmp3lame", "webm": "libvpx-vp9", "avif": "libaom-av1"}


def encoders():
    global _ENC
    if _ENC is None:
        try:
            o = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=8).stdout
            _ENC = {ln.split()[1] for ln in o.splitlines() if len(ln.split()) > 2 and ln.startswith(" ")}
        except Exception:
            _ENC = set()
    return _ENC


def targets(k, src_ext=None):
    """Target formats for a kind, minus anything this ffmpeg build cannot encode."""
    enc = encoders()
    out = [t for t in TARGETS.get(k, []) if t not in NEED or NEED[t] in enc or t == "avif" or (t == "mp3" and shutil.which("lame"))]
    return [t for t in out if t != src_ext]


def ext(p):
    n = os.path.basename(p).lower()
    for e in ("tar.gz", "tar.xz", "tar.bz2", "tar.zst"):
        if n.endswith("." + e):
            return e
    return os.path.splitext(n)[1].lstrip(".")


def kind(p):
    e = ext(p)
    if e in IMG: return "image"
    if e in VID: return "video"
    if e in AUD: return "audio"
    if e in ARC or e.startswith("tar."): return "archive"
    return None


def outname(src, dst_ext, outdir=None):
    d = outdir or os.path.dirname(src)
    os.makedirs(d, exist_ok=True)
    stem = os.path.basename(src)
    e = ext(src)
    stem = stem[:-(len(e) + 1)] if e and stem.lower().endswith("." + e) else stem
    out = os.path.join(d, f"{stem}.{dst_ext}")
    n = 1
    while os.path.exists(out):
        out = os.path.join(d, f"{stem} ({n}).{dst_ext}"); n += 1
    return out


def duration(p):
    try:
        o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                           capture_output=True, text=True, timeout=8).stdout.strip()
        return float(o)
    except Exception:
        return 0.0


A_ARGS = {
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"], "wav": ["-c:a", "pcm_s16le"], "flac": ["-c:a", "flac"],
    "ogg": ["-c:a", "vorbis", "-strict", "-2", "-b:a", "192k"], "opus": ["-c:a", "libopus", "-b:a", "128k"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"], "aac": ["-c:a", "aac", "-b:a", "192k"],
}
V_ARGS = {
    "mp4": ["-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"],
    "mov": ["-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac"],
    "mkv": ["-c:v", "libx264", "-crf", "20", "-c:a", "aac"],
    "webm": ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus"],
    "avi": ["-c:v", "mpeg4", "-q:v", "4", "-c:a", "aac"],
}


def ffmpeg(src, dst, dext, k, progress=None):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-progress", "pipe:1", "-nostats"]
    if dext in A_ARGS:
        cmd += ["-vn"] + A_ARGS[dext]
    elif dext == "gif":
        cmd += ["-vf", "fps=15,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse"] if k == "video" else []
    elif dext in V_ARGS:
        cmd += V_ARGS[dext]
        if k == "image":
            cmd += ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
    elif k == "image" and not (ext(src) == "gif" and dext in ("webp", "gif")):
        cmd += ["-frames:v", "1"]
        if dext == "avif":
            cmd += ["-c:v", "libaom-av1", "-still-picture", "1", "-crf", "28"]
        elif dext in ("jpg", "jpeg"):
            cmd += ["-q:v", "2"]
    cmd.append(dst)
    total = duration(src) if k in ("video", "audio") else 0.0
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for ln in p.stdout:
        if progress and total and ln.startswith("out_time_us="):
            try:
                progress(min(0.99, int(ln.split("=")[1]) / 1e6 / total))
            except ValueError:
                pass
    err = p.stderr.read()
    p.wait()
    return p.returncode == 0 and os.path.exists(dst), err.strip().splitlines()[-1] if err.strip() else ""


def via_lame(src, dst, progress=None):
    """This ffmpeg has no mp3 encoder: decode to wav, encode with the lame binary."""
    tmp = tempfile.mktemp(suffix=".wav", prefix="rice-conv-")
    try:
        ok, err = ffmpeg(src, tmp, "wav", "audio", progress)
        if not ok:
            return False, err
        r = subprocess.run(["lame", "--quiet", "-V2", tmp, dst], capture_output=True, text=True)
        return r.returncode == 0 and os.path.exists(dst), r.stderr.strip()[:160]
    finally:
        try: os.remove(tmp)
        except OSError: pass


def magick(src, dst):
    s = src + ("[0]" if ext(src) in ("gif", "pdf", "ico") else "")
    r = subprocess.run(["magick", "-background", "none", "-density", "192", s, dst], capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(dst), r.stderr.strip()[:160]


def pil(src, dst, dext):
    from PIL import Image
    im = Image.open(src)
    if dext in ("pdf", "jpg", "jpeg", "bmp"):
        im = im.convert("RGB")
    im.save(dst)
    return os.path.exists(dst), ""


def archive(src, dst, dext):
    tmp = tempfile.mkdtemp(prefix="rice-conv-")
    try:
        r = subprocess.run(["7z", "x", "-y", f"-o{tmp}", src], capture_output=True, text=True)
        if r.returncode:
            return False, "cannot read archive"
        if dext == "zip":
            r = subprocess.run(["7z", "a", "-tzip", dst, "."], cwd=tmp, capture_output=True, text=True)
        elif dext == "7z":
            r = subprocess.run(["7z", "a", "-t7z", dst, "."], cwd=tmp, capture_output=True, text=True)
        else:
            flag = {"tar": "cf", "tar.gz": "czf", "tar.xz": "cJf"}[dext]
            r = subprocess.run(["tar", flag, dst, "-C", tmp, "."], capture_output=True, text=True)
        return r.returncode == 0 and os.path.exists(dst), r.stderr.strip()[:160]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def convert(src, dext, progress=None, outdir=None):
    """-> (ok, outpath_or_error)"""
    k = kind(src)
    if ext(src) == dext:
        return False, "already " + dext
    dst = outname(src, dext, outdir)
    err = ""
    chain = []
    if k == "archive":
        chain = [lambda: archive(src, dst, dext)]
    elif k == "image":
        e = ext(src)
        if dext == "pdf":
            chain = [lambda: pil(src, dst, dext), lambda: magick(src, dst)]
        elif e == "svg" or dext == "ico":
            chain = [lambda: magick(src, dst), lambda: ffmpeg(src, dst, dext, k, progress)]
        else:
            chain = [lambda: ffmpeg(src, dst, dext, k, progress), lambda: magick(src, dst), lambda: pil(src, dst, dext)]
    elif k in ("video", "audio"):
        chain = [lambda: ffmpeg(src, dst, dext, k, progress)]
        if dext == "mp3" and "libmp3lame" not in encoders() and shutil.which("lame"):
            chain = [lambda: via_lame(src, dst, progress)]
    else:   # unknown: try everything
        chain = [lambda: ffmpeg(src, dst, dext, k or "video", progress), lambda: magick(src, dst)]
    for step in chain:
        try:
            ok, err = step()
        except Exception as e:
            ok, err = False, str(e)
        if ok:
            return True, dst
        try:
            os.remove(dst)
        except OSError:
            pass
    return False, err or "conversion failed"
