"""
Sport Reel Generator — Follow the Money
Usage: python reel_template/make_sport_reel.py reels/<name>

Each reel folder needs a reel_config.py with a CONFIG dict.
Sport-specific keys:
  vibe          "sport_dark" | "broadcast" | "champions" | "stadium_night" | "finance_sport"
  image_layout  "fullbleed" | "duo_v" | "duo_h" | "trio" | "mosaic" | "hero_accent"
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import glob, importlib.util, os, random, subprocess, sys


# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

W, H   = 1080, 1920   # frame dimensions
PAD_L  = 54            # left text margin
PAD_R  = 54            # right text margin
TEXT_W = W - PAD_L - PAD_R
GAP    = 6             # pixel gap between image panels in multi-layouts


# ─────────────────────────────────────────────────────────────
# Palettes
# ─────────────────────────────────────────────────────────────

SPORT_PALETTES = {
    "sport_dark": {
        "accent":         (255, 220,   0),
        "text_hero":      (255, 255, 255),
        "text_label":     (200, 200, 200),
        "text_dim":       (100, 100, 110),
        "text_tag":       (255, 220,   0),
        "divider":        ( 40,  40,  45),
        "color_sat": 0.80, "color_con": 1.15,
        "red_shift": 0.95, "blue_shift": 1.05, "blue_lift":  5,
    },
    "broadcast": {
        "accent":         (220,  30,  40),
        "text_hero":      (255, 255, 255),
        "text_label":     (210, 205, 205),
        "text_dim":       (120, 100, 100),
        "text_tag":       (255, 130, 130),
        "divider":        ( 50,  30,  30),
        "color_sat": 0.75, "color_con": 1.18,
        "red_shift": 1.06, "blue_shift": 0.90, "blue_lift": -5,
    },
    "champions": {
        "accent":         (210, 175,  55),
        "text_hero":      (240, 240, 255),
        "text_label":     (185, 190, 225),
        "text_dim":       ( 80,  90, 140),
        "text_tag":       (210, 175,  55),
        "divider":        ( 25,  30,  65),
        "color_sat": 0.72, "color_con": 1.12,
        "red_shift": 0.92, "blue_shift": 1.12, "blue_lift": 10,
    },
    "stadium_night": {
        "accent":         (  0, 220,  80),
        "text_hero":      (255, 255, 255),
        "text_label":     (190, 215, 190),
        "text_dim":       ( 80, 115,  80),
        "text_tag":       (  0, 220,  80),
        "divider":        ( 20,  38,  20),
        "color_sat": 0.68, "color_con": 1.20,
        "red_shift": 0.88, "blue_shift": 0.95, "blue_lift":  0,
    },
    "finance_sport": {
        "accent":         (255, 215,   0),
        "text_hero":      (240, 242, 255),
        "text_label":     (180, 190, 230),
        "text_dim":       ( 70,  85, 145),
        "text_tag":       (255, 215,   0),
        "divider":        ( 22,  28,  60),
        "color_sat": 0.65, "color_con": 1.15,
        "red_shift": 0.92, "blue_shift": 1.10, "blue_lift": 10,
    },
}

DEFAULT_VIBE = "finance_sport"


# ─────────────────────────────────────────────────────────────
# Config loader
# ─────────────────────────────────────────────────────────────

def load_config(reel_dir):
    config_path = os.path.join(reel_dir, "reel_config.py")
    if not os.path.exists(config_path):
        print(f"  ✗ No reel_config.py found in: {reel_dir}")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("reel_config", config_path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cfg = dict(mod.CONFIG)

    fonts_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    cfg.setdefault("input_folder",       os.path.join(reel_dir, "images"))
    cfg.setdefault("output_folder",      os.path.join(reel_dir, "output"))
    cfg.setdefault("fonts_folder",       fonts_path)
    cfg.setdefault("fps",                30)
    cfg.setdefault("hold_seconds",       3.0)
    cfg.setdefault("fade_seconds",       0.5)
    cfg.setdefault("make_image",         True)
    cfg.setdefault("make_video",         True)
    cfg.setdefault("vibe",               DEFAULT_VIBE)
    cfg.setdefault("image_layout",       "fullbleed")
    cfg.setdefault("caption_all_frames", False)
    cfg.setdefault("cover_hold_seconds", 0.0)
    cfg.setdefault("transitions_enabled",False)

    vibe = cfg["vibe"]
    if vibe not in SPORT_PALETTES:
        print(f"  ⚠ Vibe '{vibe}' not found — using {DEFAULT_VIBE}")
        cfg["vibe"] = DEFAULT_VIBE

    return cfg


# ─────────────────────────────────────────────────────────────
# Font loader
# ─────────────────────────────────────────────────────────────

def load_sport_fonts(fonts_dir, scale=1.0, overrides=None):
    _FALLBACK_ORDER = [
        "BigShoulders-Bold.ttf", "WorkSans-Bold.ttf",
        "Outfit-Bold.ttf",       "NotoSans-Regular.ttf",
    ]

    def f(name, size):
        path = os.path.join(fonts_dir, name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
        for fb in _FALLBACK_ORDER:
            fp = os.path.join(fonts_dir, fb)
            if os.path.exists(fp):
                return ImageFont.truetype(fp, size)
        return ImageFont.load_default()

    s = scale
    fonts = {
        "display":    f("BigShoulders-Bold.ttf", int(118 * s)),
        "display_sm": f("BigShoulders-Bold.ttf", int( 80 * s)),
        "heading":    f("WorkSans-Bold.ttf",      int( 38 * s)),
        "heading_sm": f("WorkSans-Bold.ttf",      int( 28 * s)),
        "tag":        f("Tektur-Medium.ttf",       int( 22 * s)),
        "tag_sm":     f("Tektur-Medium.ttf",       int( 16 * s)),
        "mono":       f("GeistMono-Regular.ttf",   int( 18 * s)),
        "hook":       f("WorkSans-Bold.ttf",       int( 52 * s)),
        "hook_sm":    f("WorkSans-Bold.ttf",       int( 38 * s)),
    }
    if overrides:
        for key, (fname, size) in overrides.items():
            fonts[key] = f(fname, int(size * s))
    return fonts


# ─────────────────────────────────────────────────────────────
# Text helpers
# ─────────────────────────────────────────────────────────────

_MEASURE = ImageDraw.Draw(Image.new("RGB", (1, 1)))


def _tw(text, font):
    bb = _MEASURE.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _th(text, font):
    bb = _MEASURE.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _wrap(text, font, max_width):
    words = text.split()
    lines, cur = [], []
    for word in words:
        test = " ".join(cur + [word])
        if _tw(test, font) <= max_width:
            cur.append(word)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))
    return lines


def _draw_left(draw, x, y, text, font, fill):
    if text:
        draw.text((x, y), text, font=font, fill=fill)


def _draw_wrapped(draw, x, y, text, font, fill, max_width, gap=8):
    if not text:
        return y
    for line in _wrap(text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        y += _th(line, font) + gap
    return y


def _wrapped_h(text, font, max_width, gap=8):
    if not text:
        return 0
    lines = _wrap(text, font, max_width)
    total = sum(_th(ln, font) for ln in lines)
    return total + gap * (len(lines) - 1)


# ─────────────────────────────────────────────────────────────
# Photo helpers
# ─────────────────────────────────────────────────────────────

def _load_photo(fpath, target_w, target_h):
    photo = Image.open(fpath).convert("RGB")
    try:
        exif = photo._getexif()
        if exif:
            ori = exif.get(274)
            if ori == 3:   photo = photo.rotate(180, expand=True)
            elif ori == 6: photo = photo.rotate(270, expand=True)
            elif ori == 8: photo = photo.rotate(90,  expand=True)
    except Exception:
        pass
    pw, ph = photo.size
    target_ratio = target_w / target_h
    if pw / ph > target_ratio:
        nw = int(ph * target_ratio)
        photo = photo.crop(((pw - nw) // 2, 0, (pw - nw) // 2 + nw, ph))
    else:
        nh = int(pw / target_ratio)
        top = max(0, (ph - nh) // 3)
        photo = photo.crop((0, top, pw, top + nh))
    return photo.resize((target_w, target_h), Image.LANCZOS)


def _grade(photo, pal):
    photo = ImageEnhance.Color(photo).enhance(pal["color_sat"])
    photo = ImageEnhance.Contrast(photo).enhance(pal["color_con"])
    r, g, b = photo.split()
    r = r.point(lambda x: max(0, min(255, int(x * pal["red_shift"]))))
    b = b.point(lambda x: max(0, min(255, int(x * pal["blue_shift"] + pal["blue_lift"]))))
    return Image.merge("RGB", (r, g, b))


def _grain(img, seed=42, alpha=0.018):
    random.seed(seed)
    noise = Image.new("L", (W, H), 128)
    for _ in range(W * H // 8):
        noise.putpixel(
            (random.randint(0, W - 1), random.randint(0, H - 1)),
            random.randint(112, 143),
        )
    noise_rgb = Image.merge("RGB", [noise, noise, noise])
    noise_rgb = noise_rgb.filter(ImageFilter.GaussianBlur(0.4))
    return Image.blend(img, noise_rgb, alpha=alpha)


# ─────────────────────────────────────────────────────────────
# Multi-image layout composers
# ─────────────────────────────────────────────────────────────

def _fullbleed(paths):
    return _load_photo(paths[0], W, H)


def _duo_v(paths):
    half = (W - GAP) // 2
    left  = _load_photo(paths[0], half, H)
    right = _load_photo(paths[1] if len(paths) > 1 else paths[0], W - half - GAP, H)
    out = Image.new("RGB", (W, H))
    out.paste(left,  (0, 0))
    out.paste(right, (half + GAP, 0))
    return out


def _duo_h(paths):
    half = (H - GAP) // 2
    top = _load_photo(paths[0], W, half)
    bot = _load_photo(paths[1] if len(paths) > 1 else paths[0], W, H - half - GAP)
    out = Image.new("RGB", (W, H))
    out.paste(top, (0, 0))
    out.paste(bot, (0, half + GAP))
    return out


def _trio(paths):
    top_h  = int(H * 0.48)
    bot_h  = H - top_h - GAP
    half_w = (W - GAP) // 2
    top      = _load_photo(paths[0], W, top_h)
    bot_left = _load_photo(paths[1] if len(paths) > 1 else paths[0], half_w, bot_h)
    bot_right= _load_photo(paths[2] if len(paths) > 2 else paths[0], W - half_w - GAP, bot_h)
    out = Image.new("RGB", (W, H))
    out.paste(top,       (0, 0))
    out.paste(bot_left,  (0, top_h + GAP))
    out.paste(bot_right, (half_w + GAP, top_h + GAP))
    return out


def _mosaic(paths):
    hw = (W - GAP) // 2
    hh = (H - GAP) // 2
    slots = [paths[i] if i < len(paths) else paths[0] for i in range(4)]
    imgs = [
        _load_photo(slots[0], hw,        hh),
        _load_photo(slots[1], W - hw - GAP, hh),
        _load_photo(slots[2], hw,        H - hh - GAP),
        _load_photo(slots[3], W - hw - GAP, H - hh - GAP),
    ]
    out = Image.new("RGB", (W, H))
    out.paste(imgs[0], (0, 0))
    out.paste(imgs[1], (hw + GAP, 0))
    out.paste(imgs[2], (0, hh + GAP))
    out.paste(imgs[3], (hw + GAP, hh + GAP))
    return out


def _hero_accent(paths):
    hero_w = int(W * 0.65)
    acc_w  = W - hero_w - GAP
    hero   = _load_photo(paths[0], hero_w, H)
    accent = _load_photo(paths[1] if len(paths) > 1 else paths[0], acc_w, H)
    out = Image.new("RGB", (W, H))
    out.paste(hero,   (0, 0))
    out.paste(accent, (hero_w + GAP, 0))
    return out


_COMPOSERS = {
    "fullbleed":   _fullbleed,
    "duo_v":       _duo_v,
    "duo_h":       _duo_h,
    "trio":        _trio,
    "mosaic":      _mosaic,
    "hero_accent": _hero_accent,
}

_LAYOUT_SLOTS = {
    "fullbleed": 1, "duo_v": 2, "duo_h": 2,
    "trio": 3, "mosaic": 4, "hero_accent": 2,
}


def compose_image_zone(paths, layout, pal):
    composer = _COMPOSERS.get(layout, _fullbleed)
    return _grade(composer(paths), pal)


# ─────────────────────────────────────────────────────────────
# Frame overlays  (gradients + chrome — no boxes)
# ─────────────────────────────────────────────────────────────

def _top_gradient(canvas, strength=180, fade_h=200):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for y in range(fade_h):
        t = 1 - y / fade_h
        a = int(strength * (t ** 1.4))
        ImageDraw.Draw(overlay).line([(0, y), (W, y)], fill=(0, 0, 0, a))
    canvas.alpha_composite(overlay)


def _bottom_gradient(canvas, strength=220, fade_h=760):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for y in range(fade_h):
        t = y / fade_h
        a = int(strength * (t ** 1.6))
        ImageDraw.Draw(overlay).line([(0, H - fade_h + y), (W, H - fade_h + y)], fill=(0, 0, 0, a))
    canvas.alpha_composite(overlay)


def _draw_top_bar(canvas, cfg, fnt, pal):
    _top_gradient(canvas)
    draw   = ImageDraw.Draw(canvas)
    handle = cfg.get("location_coords", "FOLLOW THE MONEY")
    org    = cfg.get("location_name",   "")
    ty     = 28
    _draw_left(draw, PAD_L, ty, handle.upper(), fnt["tag"], pal["text_tag"])
    if org:
        _draw_left(draw, W - _tw(org.upper(), fnt["tag"]) - PAD_R, ty, org.upper(), fnt["tag"], pal["text_label"])
    rule_y = ty + _th(handle, fnt["tag"]) + 6
    draw.line([(PAD_L, rule_y), (PAD_L + 120, rule_y)], fill=pal["accent"], width=2)


def _draw_chrome(canvas, cfg, fnt, pal):
    draw   = ImageDraw.Draw(canvas)
    y      = H - 56
    season = cfg.get("location_season", "")
    label  = cfg.get("frame_label",     "")
    draw.line([(PAD_L, y - 12), (W - PAD_R, y - 12)], fill=pal["divider"], width=1)
    if season:
        _draw_left(draw, PAD_L, y, season.upper(), fnt["mono"], pal["text_dim"])
    if label:
        _draw_left(draw, W - _tw(label, fnt["mono"]) - PAD_R, y, label, fnt["mono"], pal["text_dim"])


# ─────────────────────────────────────────────────────────────
# Caption / stat text rendering
# ─────────────────────────────────────────────────────────────

def _draw_upper_title(draw, upper_title, fnt, pal):
    _draw_left(draw, PAD_L, 90, upper_title.upper(), fnt["heading_sm"], pal["text_hero"])
    acc_y = 90 + _th(upper_title, fnt["heading_sm"]) + 6
    draw.line([(PAD_L, acc_y), (PAD_L + 80, acc_y)], fill=pal["accent"], width=3)


def _draw_hook(draw, hook_question, hook_answer, fnt, pal):
    if hook_question and not hook_answer:
        q_h = _wrapped_h(hook_question, fnt["hook"], TEXT_W, gap=10)
        _draw_wrapped(draw, PAD_L, (H - q_h) // 2 - 60, hook_question, fnt["hook"], pal["text_hero"], TEXT_W, gap=10)

    elif hook_question and hook_answer:
        ans_h   = _wrapped_h(hook_answer, fnt["hook_sm"], TEXT_W, gap=8)
        q_h     = _th(hook_question, fnt["tag_sm"])
        y       = H - 180 - q_h - 18 - ans_h
        _draw_left(draw, PAD_L, y, hook_question, fnt["tag_sm"], pal["text_dim"])
        y += q_h + 8
        draw.line([(PAD_L, y), (PAD_L + 60, y)], fill=pal["accent"], width=2)
        _draw_wrapped(draw, PAD_L, y + 10, hook_answer, fnt["hook_sm"], pal["text_hero"], TEXT_W, gap=8)

    else:  # answer only
        ans_h = _wrapped_h(hook_answer, fnt["hook_sm"], TEXT_W, gap=8)
        _draw_wrapped(draw, PAD_L, H - 180 - ans_h, hook_answer, fnt["hook_sm"], pal["text_hero"], TEXT_W, gap=8)


def _draw_stat_block(draw, tag, line1, line2, line3, line2_label, fnt, pal, col1, col2, col3, col_tag):
    GAP_SM, GAP_LG, RULE_H = 10, 18, 20
    BOTTOM = H - 100

    l3_h  = _wrapped_h(line3,       fnt["tag"],        TEXT_W, gap=7) if line3       else 0
    l2_h  = _th(line2,       fnt["heading"])                           if line2       else 0
    l1_h  = _th(line1,       fnt["display"])                           if line1       else 0
    l2l_h = _th(line2_label, fnt["heading_sm"])                        if line2_label else 0
    tag_h = _th(tag,         fnt["tag_sm"])                            if tag         else 0

    total = (
        tag_h  + (GAP_SM if tag else 0) +
        l3_h   + (RULE_H if line3 else 0) +
        l2_h   + (GAP_SM if line2 else 0) +
        l1_h   + (GAP_SM if line1 else 0) +
        l2l_h
    )
    y = BOTTOM - total

    if tag:
        _draw_left(draw, PAD_L, y, tag.upper(), fnt["tag_sm"], col_tag)
        y += tag_h + GAP_SM

    if line3:
        draw.line([(PAD_L, y), (PAD_L + 48, y)], fill=pal["accent"], width=2)
        y += RULE_H - 8
        _draw_wrapped(draw, PAD_L, y, line3, fnt["tag"], col3, TEXT_W, gap=7)
        y += l3_h + GAP_LG

    if line2_label:
        _draw_left(draw, PAD_L, y, line2_label.upper(), fnt["heading_sm"], pal["text_label"])
        y += l2l_h + GAP_SM

    if line1:
        _draw_left(draw, PAD_L, y, line1, fnt["display"], col1)
        y += l1_h + GAP_SM

    if line2:
        _draw_left(draw, PAD_L, y, line2.upper(), fnt["heading"], col2)


# ─────────────────────────────────────────────────────────────
# Frame renderer
# ─────────────────────────────────────────────────────────────

def render_sport_frame(photo_paths, cfg, fnt, show_caption=True, frame_caption=None):
    """Return a single 1080×1920 PIL Image. Text floats over gradient overlays — no boxes."""
    pal    = SPORT_PALETTES[cfg["vibe"]]
    fc     = frame_caption or {}
    layout = fc.get("image_layout", cfg.get("image_layout", "fullbleed"))

    canvas = compose_image_zone(photo_paths, layout, pal).convert("RGBA")

    _draw_top_bar(canvas, cfg, fnt, pal)
    _bottom_gradient(canvas, strength=235 if show_caption else 160)
    _draw_chrome(canvas, cfg, fnt, pal)

    draw = ImageDraw.Draw(canvas)

    tag         = fc.get("tag",         cfg.get("caption_tag",         ""))
    line1       = fc.get("line1",       cfg.get("caption_line1",       ""))
    line2       = fc.get("line2",       cfg.get("caption_line2",       ""))
    line3       = fc.get("line3",       cfg.get("caption_line3",       ""))
    line2_label = fc.get("line2_label", cfg.get("caption_line2_label", ""))
    hook_question = fc.get("hook_question")
    hook_answer   = fc.get("hook_answer", "")
    upper_title   = fc.get("upper_title", "")

    col1    = tuple(fc.get("color_line1", cfg.get("color_line1", pal["accent"])))
    col2    = tuple(fc.get("color_line2", cfg.get("color_line2", pal["text_hero"])))
    col3    = tuple(fc.get("color_line3", cfg.get("color_line3", pal["text_label"])))
    col_tag = tuple(fc.get("color_tag",   cfg.get("color_tag",   pal["text_tag"])))

    if upper_title:
        _draw_upper_title(draw, upper_title, fnt, pal)

    if hook_question or hook_answer:
        _draw_hook(draw, hook_question, hook_answer, fnt, pal)
    elif show_caption:
        _draw_stat_block(draw, tag, line1, line2, line3, line2_label, fnt, pal, col1, col2, col3, col_tag)

    return _grain(canvas.convert("RGB"))


# ─────────────────────────────────────────────────────────────
# Transitions
# ─────────────────────────────────────────────────────────────

def _ease(t):
    return t * t * (3 - 2 * t)


def _render_transition(src, dst, n_frames, kind, frames_dir, frame_i):
    for f in range(n_frames):
        t = _ease(f / n_frames)
        if kind == "crossfade":
            out = Image.blend(src, dst, alpha=t)
        else:
            out = Image.new("RGB", (W, H))
            if kind == "push_left":
                ox = int(W * t); out.paste(src, (-ox, 0)); out.paste(dst, (W - ox, 0))
            elif kind == "push_right":
                ox = int(W * t); out.paste(src, (ox, 0));  out.paste(dst, (ox - W, 0))
            elif kind == "push_up":
                oy = int(H * t); out.paste(src, (0, -oy)); out.paste(dst, (0, H - oy))
            elif kind == "push_down":
                oy = int(H * t); out.paste(src, (0, oy));  out.paste(dst, (0, oy - H))
        out.save(os.path.join(frames_dir, f"f{frame_i:05d}.png"))
        frame_i += 1
    return frame_i


# ─────────────────────────────────────────────────────────────
# Video encoding
# ─────────────────────────────────────────────────────────────

def _encode_mp4(frames_dir, out_mp4, cfg, reel_dir, frame_count):
    FPS        = cfg["fps"]
    OUTPUT_FPS = max(30, cfg.get("output_fps", 30))
    video_dur  = frame_count / FPS
    audio_dur  = min(video_dur, 55.0)
    fade_start = max(0.0, audio_dur - 2.5)

    vo_path   = os.path.join(reel_dir, "voiceover.mp3")
    has_vo    = os.path.exists(vo_path)

    this_dir    = os.path.dirname(os.path.abspath(__file__))
    music_files = sorted(
        glob.glob(os.path.join(this_dir, "music", "*.mp3")) +
        glob.glob(os.path.join(this_dir, "music", "*.m4a"))
    )
    bg_track = None
    if music_files and cfg.get("bg_music", False):
        bg_track = music_files[abs(hash(os.path.basename(reel_dir))) % len(music_files)]
        print(f"  ♪ Music: {os.path.basename(bg_track)}")

    bg_vol = cfg.get("bg_music_volume", 0.12 if has_vo else 0.20)

    def _base_cmd(*extra):
        return [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", os.path.join(frames_dir, "f%05d.png"),
            *extra,
            "-r", str(OUTPUT_FPS),
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-vf", f"scale={W}:{H}",
            out_mp4,
        ]

    if has_vo and bg_track:
        af = (
            f"[1:a]volume=1.0[vo];"
            f"[2:a]aloop=loop=-1:size=2e+09,volume={bg_vol},"
            f"atrim=duration={audio_dur:.2f},afade=t=out:st={fade_start:.2f}:d=2.5[bg];"
            f"[vo][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        cmd = _base_cmd("-i", vo_path, "-stream_loop", "-1", "-i", bg_track,
                        "-filter_complex", af, "-map", "0:v", "-map", "[aout]",
                        "-c:a", "aac", "-b:a", "192k")
    elif has_vo:
        cmd = _base_cmd("-i", vo_path,
                        "-filter_complex", "[1:a]volume=1.0[aout]",
                        "-map", "0:v", "-map", "[aout]", "-c:a", "aac", "-b:a", "192k")
    elif bg_track:
        af = (
            f"[1:a]aloop=loop=-1:size=2e+09,volume={bg_vol},"
            f"atrim=duration={audio_dur:.2f},afade=t=out:st={fade_start:.2f}:d=2.5[aout]"
        )
        cmd = _base_cmd("-stream_loop", "-1", "-i", bg_track,
                        "-filter_complex", af, "-map", "0:v", "-map", "[aout]",
                        "-c:a", "aac", "-b:a", "192k")
    else:
        cmd = _base_cmd()

    print(f"\n▸ Encoding MP4 ({frame_count} frames @ {FPS}fps → {OUTPUT_FPS}fps)...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        size_mb = os.path.getsize(out_mp4) / 1024 / 1024
        print(f"  ✓ {out_mp4}  ({size_mb:.1f} MB)")
    else:
        print(f"  ✗ ffmpeg error:\n{result.stderr[-600:]}")


# ─────────────────────────────────────────────────────────────
# Frame sequence renderer
# ─────────────────────────────────────────────────────────────

def _render_frames(cfg, photo_files, fnt, frames_dir):
    """Write all frame PNGs to frames_dir. Returns total frame count."""
    FPS            = cfg["fps"]
    per_frame_caps = cfg.get("per_frame_captions")
    always_caption = cfg.get("caption_all_frames", False)
    n_total        = len(per_frame_caps) if per_frame_caps else len(photo_files)

    def _frame_cap(i):
        if per_frame_caps:
            fc   = per_frame_caps[i] if i < len(per_frame_caps) else None
            show = (fc or {}).get("show_caption", True) if fc else False
            return show, fc
        return always_caption or (i == 0), None

    def _photos_for(i, fc):
        layout  = (fc or {}).get("image_layout", cfg.get("image_layout", "fullbleed"))
        n       = _LAYOUT_SLOTS.get(layout, 1)
        indices = (fc or {}).get("images")
        if indices:
            return [photo_files[j % len(photo_files)] for j in indices]
        start = i * n
        return [photo_files[(start + k) % len(photo_files)] for k in range(n)]

    _TRANSITIONS    = ["push_left", "push_up", "push_right", "crossfade"]
    _trng           = random.Random()
    _last_trans     = None
    frame_i         = 0
    FADE_F          = int(cfg["fade_seconds"] * FPS)

    # Cover frame (thumbnail bait)
    cover_hold = cfg.get("cover_hold_seconds", 0.0)
    if cover_hold > 0:
        last_fc    = (per_frame_caps or [None])[-1]
        last_show  = (last_fc or {}).get("show_caption", True) if last_fc else True
        cover_f    = render_sport_frame(_photos_for(n_total - 1, last_fc), cfg, fnt,
                                         show_caption=last_show, frame_caption=last_fc)
        for _ in range(int(cover_hold * FPS)):
            cover_f.save(os.path.join(frames_dir, f"f{frame_i:05d}.png"))
            frame_i += 1
        print(f"  ✓ Cover frame ({cover_hold}s)")

    for i in range(n_total):
        show, fc = _frame_cap(i)
        paths    = _photos_for(i, fc)
        hold_f   = int((fc or {}).get("hold_seconds", cfg["hold_seconds"]) * FPS)

        # Word-by-word reveal for hook answers
        all_words = ((fc or {}).get("hook_answer", "") or "").split()
        if all_words and hold_f > 1:
            base = None
            for k in range(hold_f):
                n_shown    = max(1, min(len(all_words), k // 2 + 1))
                partial_fc = {**(fc or {}), "hook_answer": " ".join(all_words[:n_shown])}
                base = render_sport_frame(paths, cfg, fnt, show_caption=show, frame_caption=partial_fc)
                base.save(os.path.join(frames_dir, f"f{frame_i:05d}.png"))
                frame_i += 1
        else:
            base = render_sport_frame(paths, cfg, fnt, show_caption=show, frame_caption=fc)
            for _ in range(hold_f):
                base.save(os.path.join(frames_dir, f"f{frame_i:05d}.png"))
                frame_i += 1

        # Optional transition to next frame
        if i < n_total - 1 and cfg.get("transitions_enabled", False):
            next_show, next_fc = _frame_cap(i + 1)
            next_base = render_sport_frame(_photos_for(i + 1, next_fc), cfg, fnt,
                                            show_caption=next_show, frame_caption=next_fc)
            allowed    = cfg.get("transitions", _TRANSITIONS)
            kind       = _trng.choice([t for t in allowed if t != _last_trans] or allowed)
            _last_trans = kind
            frame_i    = _render_transition(base, next_base, FADE_F, kind, frames_dir, frame_i)
            print(f"    → transition: {kind}")

        print(f"  {i + 1}/{n_total}: frame {frame_i}")

    return frame_i


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python reel_template/make_sport_reel.py reels/<name>")
        sys.exit(1)

    reel_dir = os.path.abspath(sys.argv[1])
    cfg      = load_config(reel_dir)
    os.makedirs(cfg["output_folder"], exist_ok=True)

    print("═" * 62)
    print("  SPORT REEL GENERATOR — Follow the Money")
    print(f"  Vibe: {cfg['vibe']}  |  Layout: {cfg.get('image_layout', 'fullbleed')}")
    print("═" * 62)

    fnt = load_sport_fonts(cfg["fonts_folder"], scale=cfg.get("font_scale", 1.0),
                           overrides=cfg.get("fonts_override"))

    print(f"\n▸ Scanning {cfg['input_folder']}...")
    photo_files = sorted(
        os.path.join(cfg["input_folder"], f)
        for f in os.listdir(cfg["input_folder"])
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    )
    if not photo_files:
        print("  ✗ No photos found in input_folder")
        sys.exit(1)
    print(f"  Found {len(photo_files)} photos")

    per_frame_caps = cfg.get("per_frame_captions")
    n_total        = len(per_frame_caps) if per_frame_caps else len(photo_files)

    if cfg["make_image"]:
        print("\n▸ Generating static image...")
        last_fc   = (per_frame_caps or [None])[-1]
        last_show = (last_fc or {}).get("show_caption", True) if last_fc else True
        layout    = (last_fc or {}).get("image_layout", cfg.get("image_layout", "fullbleed"))
        n         = _LAYOUT_SLOTS.get(layout, 1)
        paths     = [photo_files[((n_total - 1) * n + k) % len(photo_files)] for k in range(n)]
        frame     = render_sport_frame(paths, cfg, fnt, show_caption=last_show, frame_caption=last_fc)
        out_img   = os.path.join(cfg["output_folder"], "reel.png")
        frame.save(out_img, "PNG", dpi=(300, 300))
        print(f"  ✓ {out_img}")

    if cfg["make_video"]:
        print("\n▸ Rendering video frames...")
        frames_dir = os.path.join(cfg["output_folder"], "_frames")
        os.makedirs(frames_dir, exist_ok=True)
        frame_count = _render_frames(cfg, photo_files, fnt, frames_dir)
        _encode_mp4(frames_dir, os.path.join(cfg["output_folder"], "reel.mp4"),
                    cfg, reel_dir, frame_count)

    print("\n" + "═" * 62)
    print(f"  DONE!  Output: {cfg['output_folder']}")
    print("═" * 62)


if __name__ == "__main__":
    main()
