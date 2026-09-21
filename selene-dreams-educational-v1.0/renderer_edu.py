# =============================================================================
# renderer_edu.py — deterministic slide compositor (backgrounds + typography)
# VERSION 1.6 — 2026-09-09
# CHANGELOG
#   1.6  2026-09-09  SCRIM THE TEXT, NOT THE ZONE. v1.5 measured and darkened the
#                    whole zone box — 940px wide for a centred cover line — so a
#                    short description centred over a bright highlight had its
#                    reading averaged with the darker edges either side, and the
#                    correction landed spread thin and too weak. The scrim now
#                    follows the actual laid-out lines: their real width, their
#                    real position. Same idea, aimed properly.
#   1.5  2026-09-09  PER-ZONE SCRIM. v1.4 measured the whole text block as ONE
#                    region, so on a cover whose title sits over a mid-toned area
#                    and whose description sits over a washed-out one, the average
#                    came out mid and the description stayed unreadable. Each zone
#                    is now measured and corrected on its own. Also lifted the
#                    correction curve: the first real photo tested (IMG-0003,
#                    luminance 151) earned only 15% strength, which was not enough
#                    to carry white type.
#   1.4  2026-09-09  ADAPTIVE DARKENING — white type no longer disappears on a
#                    pale photograph. Tagging the library showed most of Marcus's
#                    archive is "pale frame", which is exactly what the templates
#                    handled worst: the bubble's veil LIGHTENED the region behind
#                    white text, and the covers had no scrim at all.
#                    Marcus's call: darken rather than shrink the usable archive.
#                      _frosted() now measures the blurred panel region and, when
#                      it is light, veils toward MOSS instead of winter white,
#                      with the strength scaled to how pale it is. A dark photo is
#                      untouched, so nothing that already worked changes.
#                      _soft_scrim() is new: covers get a feathered darkening
#                      behind their text block, applied ONLY when the region under
#                      it is light. Invisible on the photos that already worked.
#                    Both are continuous, not a switch, so there is no visible
#                    step between a frame that just triggers it and one that
#                    just does not.
#   1.3  2026-08-29  STACKED PANELS. The bubble now sizes ITSELF to its text and
#                    the lines stack with one fixed gap, anchored to the panel's
#                    bottom edge — a one-line title no longer leaves a hole
#                    above the description. Matches the reference posts.
#   1.2  2026-08-29  Rebuilt to the reference set: frosted panel, rule, zone
#                    x/w/anchor/ink.
#   1.1  2026-08-28  Ink colour reacts to dark FLAT backgrounds.
#   1.0  2026-08-28  First release.
# =============================================================================
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import config_edu as C
from templates_edu import TEMPLATES


class OverflowError2(Exception):
    """Copy busts a zone's character cap or line limit — rewrite, never shrink."""


_font_cache = {}


def _font(role, size):
    key = (role, size)
    if key in _font_cache:
        return _font_cache[key]
    if role == "roumald_bold":
        f = ImageFont.truetype(C.ROUMALD_BOLD, size)
    elif role == "roumald_roman":
        f = ImageFont.truetype(C.ROUMALD_ROMAN, size)
    elif role == "roumald_italic":
        f = ImageFont.truetype(C.ROUMALD_ITALIC, size)
    else:
        f = ImageFont.truetype(C.INTER_VARIABLE, size)
        try:
            f.set_variation_by_name("Regular")
        except Exception:
            pass
    _font_cache[key] = f
    return f


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _cover_crop(img, w, h):
    sw, sh = img.size
    scale = max(w / sw, h / sh)
    img = img.resize((round(sw * scale), round(sh * scale)), Image.LANCZOS)
    left = (img.width - w) // 2
    top = (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def _wrap(draw, text, font, max_width):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _region_luminance(img, box):
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width, x1), min(img.height, y1)
    if x1 <= x0 or y1 <= y0:
        return 255
    region = img.crop((x0, y0, x1, y1)).convert("L").resize((16, 16))
    return sum(region.getdata()) / 256.0


def _measure(draw, spec, texts, W, box_w):
    """Validate caps and lay every zone out into (zone, lines, line_h, block_h)."""
    blocks = []
    for z in spec["zones"]:
        text = (texts.get(z["name"]) or "").strip()
        if not text:
            if z.get("optional"):
                continue
            raise OverflowError2(f"{z['name']}: required text missing")
        if len(text) > z["max_chars"]:
            raise OverflowError2(
                f"{z['name']}: {len(text)} chars > cap {z['max_chars']}")
        if z.get("upper"):
            text = text.upper()
        font = _font(z["font"], z["size"])
        width = z.get("w", 1.0) * W if "w" in z else box_w
        lines = _wrap(draw, text, font, width)
        if "max_lines" in z and len(lines) > z["max_lines"]:
            raise OverflowError2(
                f"{z['name']}: {len(lines)} lines > {z['max_lines']}")
        line_h = round(z["size"] * z.get("leading", 1.2))
        blocks.append((z, font, lines, line_h, line_h * len(lines), width))
    return blocks


# --- adaptive darkening (v1.4) ----------------------------------------------
# White type is set on every photo-backed template. Over a pale frame it vanishes.
# These two helpers add darkness in proportion to how pale the region actually is,
# so a dark photograph renders exactly as it did before v1.4.
PALE_LUM = 125.0        # below this, the frame is already carrying white type fine
FULL_PALE_LUM = 185.0   # at or above this, apply the full correction


def _pale_factor(lum):
    """0.0 on a dark frame, 1.0 on a washed-out one, smooth in between."""
    if lum <= PALE_LUM:
        return 0.0
    return min(1.0, (lum - PALE_LUM) / (FULL_PALE_LUM - PALE_LUM))


def _soft_scrim(canvas, box, pad=70, max_alpha=0.55):
    """Feathered darkening behind a cover's text block, only where it is needed.
    Returns the pale factor used, so callers can log it."""
    x0, y0, x1, y1 = [int(v) for v in box]
    lum = _region_luminance(canvas, (x0, y0, x1, y1))
    f = _pale_factor(lum)
    if f <= 0.01:
        return 0.0
    bx0, by0 = max(0, x0 - pad), max(0, y0 - pad)
    bx1, by1 = min(canvas.width, x1 + pad), min(canvas.height, y1 + pad)
    if bx1 <= bx0 or by1 <= by0:
        return 0.0
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([bx0, by0, bx1, by1],
                                           radius=int(pad * 1.6), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(pad * 0.85))
    mask = mask.point(lambda v: int(v * max_alpha * f))
    canvas.paste(Image.new("RGB", canvas.size, _hex_rgb(C.MOSS)), (0, 0), mask)
    return f


def _frosted(canvas, box, radius, blur, tint, alpha):
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(canvas.width, x1), min(canvas.height, y1)
    region = canvas.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(blur))
    # A pale panel veiled toward winter white gets paler still, and the white type
    # on it disappears. Veil toward moss instead, in proportion to how pale it is.
    lum = sum(region.convert("L").resize((16, 16)).getdata()) / 256.0
    f = _pale_factor(lum)
    if f > 0.01:
        tint = C.MOSS
        alpha = alpha + (0.50 - alpha) * f
    if tint:
        veil = Image.new("RGB", region.size, _hex_rgb(tint))
        region = Image.blend(region, veil, alpha)
    mask = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, x1 - x0 - 1, y1 - y0 - 1], radius=radius, fill=255)
    canvas.paste(region, (x0, y0), mask)


def render_slide(template_name, texts, background=None, flat_color=None):
    spec = TEMPLATES[template_name]
    W, H = C.CANVAS_W, C.CANVAS_H

    if background is not None:
        canvas = _cover_crop(background.convert("RGB"), W, H)
    else:
        canvas = Image.new("RGB", (W, H), _hex_rgb(flat_color or C.ECRU))
    if not spec["zones"]:
        return canvas

    draw = ImageDraw.Draw(canvas)
    default_ink = _hex_rgb(C.MOSS)
    if background is None and flat_color:
        r, g, b = _hex_rgb(flat_color)
        if (0.299 * r + 0.587 * g + 0.114 * b) < 140:
            default_ink = _hex_rgb(C.WINTER)

    def ink_for(z, left, width, top, height, panelled):
        if z.get("ink") == "winter":
            return _hex_rgb(C.WINTER)
        if z.get("ink") == "moss":
            return _hex_rgb(C.MOSS)
        if background is not None and not panelled:
            lum = _region_luminance(canvas, (left, top - 20, left + width, top + height + 20))
            return _hex_rgb(C.WINTER) if lum < 150 else _hex_rgb(C.MOSS)
        return default_ink

    stack = spec.get("stack")
    if stack:
        # --- the bubble: measure first, size the panel to the text ----------
        text_x = stack["x"] * W
        text_w = stack["w"] * W
        blocks = _measure(draw, spec, texts, W, text_w)
        gap = stack.get("gap", 24)
        total = sum(b[4] for b in blocks) + gap * max(0, len(blocks) - 1)
        bottom = stack["bottom"] * H
        content_bottom = bottom - stack.get("pad_bottom", 0.026) * H
        content_top = content_bottom - total
        if background is not None:
            p = stack.get("panel", {})
            pad_x = stack.get("pad_x", 0.042) * W
            _frosted(canvas,
                     (text_x - pad_x, content_top - stack.get("pad_top", 0.030) * H,
                      text_x + text_w + pad_x, bottom),
                     p.get("radius", 62), p.get("blur", 20),
                     p.get("tint", C.WINTER), p.get("alpha", 0.16))
            draw = ImageDraw.Draw(canvas)
        y = content_top
        for z, font, lines, line_h, block_h, width in blocks:
            ink = ink_for(z, text_x, width, y, block_h, background is not None)
            for line in lines:
                x = text_x + (width - draw.textlength(line, font=font)) / 2 \
                    if z["align"] == "center" else text_x
                draw.text((x, y), line, font=font, fill=ink)
                y += line_h
            y += gap
        return canvas

    # --- fixed-position zones (cover, outro, legacy templates) --------------
    blocks = _measure(draw, spec, texts, W, W - 2 * C.MARGIN)

    # v1.5: covers carry white type with no panel behind it. Scrim EACH ZONE on
    # its own measurement — a title over a mid-toned area and a description over a
    # washed-out one need different amounts, and averaging them helps neither.
    if background is not None and blocks:
        for z, font, lines, line_h, block_h, width in blocks:
            left = z["x"] * W if "x" in z else C.MARGIN
            top = round(z["y"] * H) if z.get("anchor") == "top" else round(z["y"] * H - block_h / 2)
            # the box the TEXT actually occupies, not the zone it is allowed to use
            widest = max((draw.textlength(l, font=font) for l in lines), default=0)
            tx0 = left + (width - widest) / 2 if z["align"] == "center" else left
            _soft_scrim(canvas, (tx0, top, tx0 + widest, top + block_h))
        rule = spec.get("rule")
        if rule:
            _soft_scrim(canvas, (rule["x0"] * W, rule["y"] * H - 6,
                                 rule["x1"] * W, rule["y"] * H + 8), pad=40)
        draw = ImageDraw.Draw(canvas)

    for z, font, lines, line_h, block_h, width in blocks:
        left = z["x"] * W if "x" in z else C.MARGIN
        y0 = round(z["y"] * H) if z.get("anchor") == "top" else round(z["y"] * H - block_h / 2)
        ink = ink_for(z, left, width, y0, block_h, False)
        y = y0
        for line in lines:
            x = left + (width - draw.textlength(line, font=font)) / 2 \
                if z["align"] == "center" else left
            draw.text((x, y), line, font=font, fill=ink)
            y += line_h

    rule = spec.get("rule")
    if rule:
        rink = _hex_rgb(C.WINTER) if rule.get("ink") == "winter" else default_ink
        draw.rectangle([rule["x0"] * W, rule["y"] * H,
                        rule["x1"] * W, rule["y"] * H + rule.get("thickness", 2)], fill=rink)
    return canvas


def save_jpeg(img, path):
    """Fresh encode: no EXIF/XMP/C2PA can survive because none is ever attached."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "JPEG", quality=92, optimize=True)
    return path
