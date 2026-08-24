# -*- coding: utf-8 -*-
"""생성된 .pptx 를 다시 읽어 PNG 로 미리보고, 글자 넘침을 잡아낸다.

LibreOffice 없이도 판면을 확인하기 위한 도구다. 만들 때 쓴 근사 계산이
아니라 **파일에 실제로 기록된** 좌표·크기·글자를 실제 폰트 메트릭으로
다시 그리므로, 넘침 검사로서는 오히려 더 엄격하다.

    python qa_preview.py 강의자료.pptx --out preview --pages 1,9,30

필요 조건: Pillow. 미리보기용일 뿐 빌드에는 필요 없다.
"""

import argparse
import io
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

FONTS = {
    ("sans", False): "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    ("sans", True):  "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    ("mono", False): "/usr/share/fonts/truetype/nanum/NanumGothicCoding.ttf",
    ("mono", True):  "/usr/share/fonts/truetype/nanum/NanumGothicCodingBold.ttf",
}
EMU_IN = 914400.0
_cache = {}


def font(kind, bold, px):
    key = (kind, bold, px)
    if key not in _cache:
        path = FONTS[(kind, bold)]
        if not os.path.exists(path):
            path = FONTS[("sans", bold)]
        _cache[key] = ImageFont.truetype(path, max(px, 1))
    return _cache[key]


def _rgb(color_fmt, default=None):
    try:
        if color_fmt and color_fmt.type is not None and color_fmt.rgb is not None:
            return tuple(color_fmt.rgb)
    except (AttributeError, TypeError, ValueError):
        pass
    return default


def _fill_rgb(shape, default=None):
    try:
        f = shape.fill
        if f.type is not None and f.type == 1:          # solid
            return _rgb(f.fore_color, default)
    except (AttributeError, TypeError, ValueError):
        pass
    return default


def _runs(paragraph):
    out = []
    for r in paragraph.runs:
        rPr = r._r.find(qn("a:rPr"))
        latin = rPr.find(qn("a:latin")) if rPr is not None else None
        name = latin.get("typeface") if latin is not None else ""
        kind = "mono" if name and "Courier" in name else "sans"
        size = r.font.size.pt if r.font.size else 12.0
        col = _rgb(r.font.color, (0, 0, 0))
        out.append((r.text, kind, bool(r.font.bold), size, col))
    return out


def _wrap(runs, width_px, px_per_pt):
    """어절 단위로 감싸되, 한 어절이 폭을 넘으면 글자 단위로 자른다."""
    lines, cur, curw = [], [], 0.0
    for text, kind, bold, size, col in runs:
        f = font(kind, bold, int(round(size * px_per_pt)))
        for token in _tokens(text):
            tw = f.getlength(token)
            if curw + tw > width_px and cur and token.strip():
                lines.append((cur, curw))
                cur, curw = [], 0.0
                if not token.strip():
                    continue
            if tw > width_px:                            # 통째로도 안 들어가면 자른다
                for ch in token:
                    cw = f.getlength(ch)
                    if curw + cw > width_px and cur:
                        lines.append((cur, curw))
                        cur, curw = [], 0.0
                    cur.append((ch, kind, bold, size, col, cw))
                    curw += cw
                continue
            cur.append((token, kind, bold, size, col, tw))
            curw += tw
    if cur:
        lines.append((cur, curw))
    return lines or [([], 0.0)]


def _tokens(text):
    out, buf = [], ""
    for ch in text:
        buf += ch
        if ch == " ":
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


def draw_text_frame(dr, tf, x, y, w, h, px_per_in, warn, tag):
    px_per_pt = px_per_in / 72.0
    cy = y
    for p in tf.paragraphs:
        runs = _runs(p)
        if not runs:
            cy += 6
            continue
        lh = (p.line_spacing if isinstance(p.line_spacing, float) else 1.2)
        base = max(r[3] for r in runs)
        lines = _wrap(runs, w, px_per_pt)
        for parts, lw in lines:
            align = str(p.alignment or "")
            ox = 0.0
            if "CENTER" in align:
                ox = (w - lw) / 2
            elif "RIGHT" in align:
                ox = w - lw
            cx = x + max(ox, 0)
            for text, kind, bold, size, col, tw in parts:
                f = font(kind, bold, int(round(size * px_per_pt)))
                dr.text((cx, cy + (base - size) * px_per_pt * 0.9), text,
                        font=f, fill=tuple(col))
                cx += tw
            cy += base * lh * px_per_pt
        if p.space_after:
            cy += p.space_after.pt * px_per_pt
    over = (cy - (y + h)) / px_per_in
    if over > 0.035:
        warn.append((tag, round(over, 3)))
    return cy


def render(path, out_dir, pages=None, px_w=1500):
    prs = Presentation(path)
    W = prs.slide_width / EMU_IN
    H = prs.slide_height / EMU_IN
    px_per_in = px_w / W
    os.makedirs(out_dir, exist_ok=True)
    warnings = []
    made = []

    for idx, slide in enumerate(prs.slides, start=1):
        if pages and idx not in pages:
            continue
        bg = _rgb(slide.background.fill.fore_color, (255, 255, 255))
        img = Image.new("RGB", (px_w, int(round(H * px_per_in))), bg)
        dr = ImageDraw.Draw(img)
        warn = []
        for shp in slide.shapes:
            _draw_shape(dr, img, shp, px_per_in, warn, "s%02d" % idx)

        for tag, over in warn:
            warnings.append((idx, tag, over))
        name = os.path.join(out_dir, "slide-%02d.png" % idx)
        img.save(name)
        made.append(name)
    return made, warnings


IDENT = (0.0, 0.0, 1.0, 1.0)


def _group_transform(shp, tr):
    """그룹의 자식 좌표계(chOff/chExt) → 부모 좌표계 변환을 합성한다."""
    xf = shp._element.find(qn("p:grpSpPr")).find(qn("a:xfrm"))
    off, ext = xf.find(qn("a:off")), xf.find(qn("a:ext"))
    ch_off, ch_ext = xf.find(qn("a:chOff")), xf.find(qn("a:chExt"))
    ox, oy = int(off.get("x")), int(off.get("y"))
    cw, chh = int(ext.get("cx")), int(ext.get("cy"))
    cox, coy = int(ch_off.get("x")), int(ch_off.get("y"))
    ccw, cch = int(ch_ext.get("cx")), int(ch_ext.get("cy"))
    sx = cw / ccw if ccw else 1.0
    sy = chh / cch if cch else 1.0
    pdx, pdy, psx, psy = tr
    return (pdx + (ox - cox * sx) * psx, pdy + (oy - coy * sy) * psy,
            psx * sx, psy * sy)


def _draw_shape(dr, img, shp, ppi, warn, tag, tr=IDENT):
    if shp.shape_type == MSO_SHAPE_TYPE.GROUP:
        inner = _group_transform(shp, tr)
        for child in shp.shapes:
            _draw_shape(dr, img, child, ppi, warn, tag, inner)
        return
    dx, dy, sx, sy = tr
    x = (dx + shp.left * sx) / EMU_IN * ppi
    y = (dy + shp.top * sy) / EMU_IN * ppi
    w = (shp.width or 0) * sx / EMU_IN * ppi
    h = (shp.height or 0) * sy / EMU_IN * ppi

    if shp.shape_type == MSO_SHAPE_TYPE.PICTURE:
        try:
            im = Image.open(io.BytesIO(shp.image.blob)).convert("RGBA")
            im = im.resize((max(int(w), 1), max(int(h), 1)), Image.LANCZOS)
            img.paste(im, (int(x), int(y)), im)
        except Exception:
            dr.rectangle([x, y, x + w, y + h], outline=(200, 60, 60))
        return

    if shp.has_table:
        _draw_table(dr, shp, x, y, ppi, warn, tag, tr)
        return

    if shp.shape_type == MSO_SHAPE_TYPE.LINE or shp._element.tag.endswith("}cxnSp"):
        col = _rgb(shp.line.color, (120, 120, 120))
        wpt = shp.line.width.pt if shp.line.width else 1.0
        flip_h = shp._element.spPr.xfrm.get("flipH") == "1"
        flip_v = shp._element.spPr.xfrm.get("flipV") == "1"
        x1, x2 = (x + w, x) if flip_h else (x, x + w)
        y1, y2 = (y + h, y) if flip_v else (y, y + h)
        dr.line([x1, y1, x2, y2], fill=col, width=max(int(round(wpt * ppi / 72.0)), 1))
        return

    if shp.has_text_frame or shp._element.tag.endswith("}sp"):
        fill = _fill_rgb(shp)
        lc = _rgb(shp.line.color)
        prst = ""
        try:
            prst = shp._element.spPr.find(qn("a:prstGeom")).get("prst")
        except AttributeError:
            pass
        if prst == "ellipse":
            if fill:
                dr.ellipse([x, y, x + w, y + h], fill=fill)
            if lc:
                dr.ellipse([x, y, x + w, y + h], outline=lc, width=1)
        elif prst == "diamond":
            pts = [(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]
            dr.polygon(pts, fill=fill, outline=lc)
        elif fill or lc:
            dr.rectangle([x, y, x + w, y + h], fill=fill, outline=lc, width=1)
        if shp.has_text_frame and shp.text_frame.text.strip():
            if shp.rotation:
                _rotated_text(img, shp, x, y, w, h, ppi)
                return
            tf = shp.text_frame
            ml = (tf.margin_left or 0) / EMU_IN * ppi
            mt = (tf.margin_top or 0) / EMU_IN * ppi
            va = str(tf.vertical_anchor or "")
            ty = y + mt
            if "MIDDLE" in va:
                ty = y + h / 2 - 0.62 * ppi * 0.16
            draw_text_frame(dr, tf, x + ml, ty, max(w - 2 * ml, 8), h,
                            ppi, warn, "%s:%s" % (tag, tf.text[:16].replace("\n", " ")))


def _rotated_text(img, shp, x, y, w, h, ppi):
    """회전된 텍스트 상자 — 수평으로 그린 뒤 회전해 합성한다."""
    runs = _runs(shp.text_frame.paragraphs[0])
    if not runs:
        return
    text, kind, bold, size, col = runs[0]
    f = font(kind, bold, int(round(size * ppi / 72.0)))
    tw, th = int(f.getlength(text)) + 4, int(size * ppi / 72.0 * 1.5) + 4
    tile = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((2, 1), text, font=f, fill=tuple(col))
    tile = tile.rotate(-(shp.rotation - 360) % 360, expand=True)
    cx, cy = x + w / 2, y + h / 2
    img.paste(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)), tile)


def _draw_table(dr, shp, x, y, ppi, warn, tag, tr=IDENT):
    _, _, sx, sy = tr
    tbl = shp.table
    widths = [c.width * sx / EMU_IN * ppi for c in tbl.columns]
    heights = [r.height * sy / EMU_IN * ppi for r in tbl.rows]
    cy = y
    for ri in range(len(tbl.rows)):
        cx = x
        for ci in range(len(widths)):
            cell = tbl.cell(ri, ci)
            if cell.is_spanned:                 # 병합에 흡수된 칸은 건너뛴다
                cx += widths[ci]
                continue
            span = cell.span_width
            cw = sum(widths[ci:ci + span])
            fill = _fill_rgb(cell, (255, 255, 255))
            dr.rectangle([cx, cy, cx + cw, cy + heights[ri]], fill=fill,
                         outline=(215, 222, 226))
            ml = (cell.margin_left or 0) / EMU_IN * ppi
            mt = (cell.margin_top or 0) / EMU_IN * ppi
            draw_text_frame(dr, cell.text_frame, cx + ml, cy + mt,
                            max(cw - 2 * ml, 8), heights[ri] - 2 * mt, ppi,
                            warn, "%s:\ud45c:%s" % (tag, cell.text[:14].replace("\n", " ")))
            cx += widths[ci]
        cy += heights[ri]


def main(argv=None):
    ap = argparse.ArgumentParser(description="생성된 PPTX 를 PNG 로 미리보고 넘침을 검사한다.")
    ap.add_argument("pptx")
    ap.add_argument("--out", default="preview")
    ap.add_argument("--pages", help="예: 1,9,30-34")
    ap.add_argument("--width", type=int, default=1500)
    a = ap.parse_args(argv)
    pages = None
    if a.pages:
        pages = set()
        for part in a.pages.split(","):
            if "-" in part:
                lo, hi = part.split("-")
                pages.update(range(int(lo), int(hi) + 1))
            elif part.strip():
                pages.add(int(part))
    made, warns = render(a.pptx, a.out, pages, a.width)
    print("%d장 렌더 → %s/" % (len(made), a.out))
    if warns:
        print("\n⚠ 상자를 넘는 텍스트 (inch):")
        for idx, tag, over in sorted(warns, key=lambda v: -v[2])[:25]:
            print("   슬라이드 %-3d %-34s +%.2f" % (idx, tag[:34], over))
        print("   총 %d건" % len(warns))
    else:
        print("넘치는 텍스트 없음.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
