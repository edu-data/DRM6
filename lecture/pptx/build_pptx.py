# -*- coding: utf-8 -*-
"""강의자료 HTML → PowerPoint(.pptx) 생성기.

    python build_pptx.py                       # ../index.html → 강의자료.pptx
    python build_pptx.py --out 특강.pptx --report
    python build_pptx.py --only 1,5,28-34      # 일부만 (판면 확인용)

도해(SVG)는 figures/ 의 PNG 를 쓴다. 도해를 고쳤다면 render_figures.py 를
먼저 한 번 돌린다. 그 외에는 python-pptx 만 있으면 된다.
"""

import argparse
import math
import os
import sys

from pptx import Presentation
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Pt

import blocks as B
import theme as T
from parse_html import parse_slides

HERE = os.path.dirname(os.path.abspath(__file__))
MAG_LINE = T.blend("B5177E", "EDF1F3", 0.34)

PART_NAMES = {
    "0": "오리엔테이션", "1": "01 · 연구문제", "2": "02 · 문헌고찰",
    "3": "03 · 연구설계", "4": "04 · 표본과 표집", "5": "05 · 측정과 설문개발",
    "6": "06 · 자료분석", "7": "07 · 논문작성", "8": "08 · 실행과 심사",
    "9": "마무리",
}

# 판면이 넘칠 때: ① 도해를 먼저 줄이고 ② 그래도 넘치면 글자를 줄인다.
# 읽어야 하는 글자보다 그림을 먼저 양보시키는 편이 강의자료로서 낫다.
FIG_SCALES = [1.0, 0.94, 0.88, 0.82, 0.76, 0.70, 0.64, 0.58]
TEXT_SCALES = [1.0, 0.97, 0.94, 0.91, 0.88, 0.85, 0.82, 0.79, 0.76, 0.73, 0.70]
# 반대로 여백이 많이 남으면 조금 키운다. 판면이 허전해 보이지 않게.
UP_SCALES = [1.15, 1.10, 1.05]


def _emu(v):
    return Emu(int(round(v * 914400)))


def line(shapes, x1, y1, x2, y2, color, width=0.75, dash=None):
    c = shapes.add_connector(MSO_CONNECTOR.STRAIGHT, _emu(x1), _emu(y1),
                             _emu(x2), _emu(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    if dash:
        c.line.dash_style = dash
    c.shadow.inherit = False
    return c


def label(shapes, x, y, w, text, size, color, *, mono=False, bold=False,
          align=PP_ALIGN.LEFT, h=None):
    tf = B.textbox(shapes, x, y, w, h or (size * 1.6 / 72.0))
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = 1.2
    r = p.add_run()
    r.text = text
    B.set_font(r, size, color, bold=bold, mono=mono)
    return tf


# ─── 공통 장식 ─────────────────────────────────────────────────────────
def paint_background(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def draw_rail(slide, part):
    """좌측 항정선 — 파트 번호를 세로로 달아 위치 표시 기능을 갖는다."""
    sh = slide.shapes
    line(sh, T.RAIL_X, T.MARGIN_T, T.RAIL_X, T.BODY_BOT, T.RULE, 0.75)
    d = sh.add_shape(MSO_SHAPE.DIAMOND, _emu(T.RAIL_X - 0.043),
                     _emu(T.MARGIN_T - 0.043), _emu(0.086), _emu(0.086))
    d.fill.solid()
    d.fill.fore_color.rgb = T.PAPER
    d.line.color.rgb = T.MAG
    d.line.width = Pt(0.75)
    d.shadow.inherit = False
    if part not in ("0", "9"):
        box = sh.add_textbox(_emu(T.RAIL_X - 0.58), _emu(T.MARGIN_T + 0.52),
                             _emu(1.0), _emu(0.20))
        box.rotation = 270
        tf = box.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.word_wrap = False
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = "PART %s" % part
        B.set_font(r, 7.5, T.INK_3, mono=True)


def draw_chrome(slide, index, total, boundaries):
    """하단 항적 진행바 — 변침점(파트 경계) 눈금과 현재 위치."""
    sh = slide.shapes
    x0, x1 = 2.55, T.SLIDE_W - T.MARGIN_R - 1.25
    y = T.CHROME_Y
    label(sh, 0.52, y - 0.085, 1.9, PART_NAMES.get(
        boundaries["part_of"][index], ""), T.FS["chrome"], T.INK_3, mono=True)
    line(sh, x0, y, x1, y, T.RULE_2, 0.75)
    frac = index / max(total - 1, 1)
    if frac > 0:
        line(sh, x0, y, x0 + (x1 - x0) * frac, y, T.MAG, 1.6)
    for b in boundaries["ticks"]:
        tx = x0 + (x1 - x0) * (b / max(total - 1, 1))
        line(sh, tx, y - 0.045, tx, y + 0.045, T.INK_3, 0.6)
    cx = x0 + (x1 - x0) * frac
    d = sh.add_shape(MSO_SHAPE.DIAMOND, _emu(cx - 0.037), _emu(y - 0.037),
                     _emu(0.074), _emu(0.074))
    d.fill.solid()
    d.fill.fore_color.rgb = T.PAPER
    d.line.color.rgb = T.MAG
    d.line.width = Pt(1.0)
    d.shadow.inherit = False
    label(sh, T.SLIDE_W - T.MARGIN_R - 1.05, y - 0.085, 1.05,
          "%d / %d" % (index + 1, total), T.FS["chrome"], T.INK_3,
          mono=True, align=PP_ALIGN.RIGHT)


def add_notes(slide, text):
    if text:
        slide.notes_slide.notes_text_frame.text = text


# ─── 슬라이드 종류별 조립 ──────────────────────────────────────────────
def compose_cover(slide, d):
    sh = slide.shapes
    _compass(sh, 10.35, 3.62, 2.45)
    x = T.MARGIN_L
    label(sh, x, 1.72, 9.0, d["kicker"], T.FS["cover_kicker"], T.MAG, mono=True)
    tf = B.textbox(sh, x, 2.02, 8.6, 1.65)
    B.put_runs(tf, d["h1"], T.FS["cover_h1"], T.INK, line_h=1.14)
    for p in tf.paragraphs:
        for r in p.runs:
            r.font.bold = True
    label(sh, x, 3.86, 8.6, d["sub"], T.FS["cover_sub"], T.INK_2, bold=True)
    mx = x
    for key, val in d["meta"]:
        label(sh, mx, 4.62, 2.6, key, T.FS["caption"], T.INK_3, mono=True)
        label(sh, mx, 4.84, 2.6, val, T.FS["cover_meta"], T.INK, bold=True)
        mx += max(T.em_width(val) * T.FS["cover_meta"] / 72.0,
                  T.em_width(key) * T.FS["caption"] / 72.0) + 0.42


def _compass(shapes, cx, cy, R):
    """표지 나침도 — 도형으로 그려 편집 가능한 상태로 둔다."""
    for f in (0.42, 0.68, 1.0):
        r = R * f
        o = shapes.add_shape(MSO_SHAPE.OVAL, _emu(cx - r), _emu(cy - r),
                             _emu(2 * r), _emu(2 * r))
        o.fill.background()
        o.line.color.rgb = T.RULE_2
        o.line.width = Pt(0.75)
        o.shadow.inherit = False
    deg = 0.0
    while deg < 360:
        a = math.radians(deg - 90)
        major = abs(deg % 45) < 0.01
        r0 = R * (0.68 if major else 0.92)
        line(shapes, cx + math.cos(a) * r0, cy + math.sin(a) * r0,
             cx + math.cos(a) * R, cy + math.sin(a) * R, T.RULE_2, 0.5)
        deg += 7.5
    for i in range(8):
        a = math.radians(i * 45 - 90)
        line(shapes, cx, cy, cx + math.cos(a) * R * 1.16,
             cy + math.sin(a) * R * 1.16, MAG_LINE, 0.75)
    nw, ntop, nbot = R * 0.13, cy - R * 0.42, cy + R * 0.16
    n = shapes.add_shape(MSO_SHAPE.DIAMOND, _emu(cx - nw / 2), _emu(ntop),
                         _emu(nw), _emu(nbot - ntop))
    n.fill.solid()
    n.fill.fore_color.rgb = T.MAG
    n.line.fill.background()
    n.shadow.inherit = False


def compose_part(slide, d):
    sh = slide.shapes
    x = T.MARGIN_L
    label(sh, x, 1.72, 3.0, d["pno"], T.FS["part_no"], T.MAG, mono=True, h=1.0)
    label(sh, x, 2.72, 9.5, d["h2"], T.FS["part_h"], T.INK, bold=True, h=0.85)
    label(sh, x, 3.62, 9.5, d["pen"], T.FS["part_en"], T.INK_3, mono=True)
    tf = B.textbox(sh, x, 4.06, 7.4, 1.1)
    p = tf.paragraphs[0]
    p.line_spacing = T.LINE_H
    r = p.add_run()
    r.text = d["lead"]
    B.set_font(r, T.FS["part_lead"], T.INK_2)
    if d["chips"]:
        B.draw(sh, {"t": "chips", "items": [(c, False) for c in d["chips"]]},
               x, 5.28, 10.0, 1.0)


def compose_content(slide, d, report):
    sh = slide.shapes
    y = T.MARGIN_T
    if d["eyebrow"]:
        label(sh, T.MARGIN_L, y, 8.0, d["eyebrow"], T.FS["eyebrow"], T.MAG, mono=True)
        y += 0.235

    title_txt = B.plain(d["h2"])
    tsize = T.FS["title"]
    tw = T.CONTENT_W * 0.94
    while tsize > 19 and T.wrapped_lines(title_txt, tsize, tw) > 2:
        tsize -= 1.0
    th = T.text_height(title_txt, tsize, tw, 1.22)
    tf = B.textbox(sh, T.MARGIN_L, y, tw, th + 0.08)
    B.put_runs(tf, d["h2"], tsize, T.INK, line_h=1.22)
    for p in tf.paragraphs:
        for r in p.runs:
            r.font.bold = True
    y += th + 0.09

    if d["lead"]:
        lw = min(T.CONTENT_W, 9.4)
        lh = T.text_height(B.plain(d["lead"]), T.FS["lead"], lw)
        tf = B.textbox(sh, T.MARGIN_L, y, lw, lh + 0.06)
        B.put_runs(tf, d["lead"], T.FS["lead"], T.INK_2)
        y += lh + 0.15
    else:
        y += 0.06

    avail = T.BODY_BOT - y
    fit = _fit(d["blocks"], T.CONTENT_W, avail)
    if fit is None:
        over = B._stack_h(d["blocks"], T.CONTENT_W, TEXT_SCALES[-1], FIG_SCALES[-1])
        report.append((d["title"], round(over - avail, 2)))
        fit = (TEXT_SCALES[-1], FIG_SCALES[-1])
    ts, fgs = fit
    B._stack(sh, d["blocks"], T.MARGIN_L, y, T.CONTENT_W, ts, fgs)
    return fit


def _fit(blocks, w, avail):
    """(글자 배율, 도해 배율) 을 찾는다.

    여유가 있으면 키우고, 넘치면 도해부터 줄인 뒤 마지막에 글자를 줄인다.
    """
    for us in UP_SCALES:
        if B._stack_h(blocks, w, us, us) <= avail:
            return us, us
    for fgs in FIG_SCALES:
        if B._stack_h(blocks, w, 1.0, fgs) <= avail:
            return 1.0, fgs
    for ts in TEXT_SCALES[1:]:
        for fgs in FIG_SCALES:
            if B._stack_h(blocks, w, ts, min(fgs, ts)) <= avail:
                return ts, min(fgs, ts)
    return None


# ─── 덱 ────────────────────────────────────────────────────────────────
def build(html_path, out_path, only=None, notes=True, verbose=False):
    slides = parse_slides(html_path)
    total = len(slides)
    boundaries = {"ticks": [], "part_of": [s["part"] for s in slides]}
    last = None
    for i, s in enumerate(slides):
        if s["part"] != last:
            boundaries["ticks"].append(i)
            last = s["part"]

    if only:
        keep = set(only)
        selected = [(i, s) for i, s in enumerate(slides) if i + 1 in keep]
    else:
        selected = list(enumerate(slides))

    prs = Presentation()
    prs.slide_width = _emu(T.SLIDE_W)
    prs.slide_height = _emu(T.SLIDE_H)
    blank = prs.slide_layouts[6]

    report, scales = [], []
    for i, d in selected:
        slide = prs.slides.add_slide(blank)
        paint_background(slide, T.PAPER_2 if d["kind"] == "part" else T.PAPER)
        draw_rail(slide, d["part"])
        if d["kind"] == "cover":
            compose_cover(slide, d)
        elif d["kind"] == "part":
            compose_part(slide, d)
        else:
            scales.append((d["title"],) + compose_content(slide, d, report))
        draw_chrome(slide, i, total, boundaries)
        if notes:
            add_notes(slide, d["note"])

    prs.save(out_path)

    tight = sorted([x for x in scales if x[1] < 1.0 or x[2] < 1.0],
                   key=lambda v: (v[1], v[2]))[:10]
    if verbose:
        print("슬라이드 %d장 → %s" % (len(selected), out_path))
        if tight:
            print("\n축소가 적용된 슬라이드 (글자/도해 배율):")
            for name, ts, fgs in tight:
                print("   %-28s %.2f / %.2f" % (name[:28], ts, fgs))
        if report:
            print("\n⚠ 최소 배율에서도 넘치는 슬라이드 (inch):")
            for name, over in report:
                print("   %-28s +%.2f" % (name[:28], over))
        else:
            print("\n넘치는 슬라이드 없음.")
    return len(selected), report


def _parse_only(spec):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="강의자료 HTML 을 PPTX 로 변환한다.")
    ap.add_argument("--html", default=os.path.join(HERE, "..", "index.html"),
                    help="원본 강의자료 HTML")
    ap.add_argument("--out", default="조사연구방법과_논문작성법.pptx", help="출력 파일")
    ap.add_argument("--only", help="일부 슬라이드만 (예: 1,5,28-34)")
    ap.add_argument("--no-notes", action="store_true", help="발표자 노트 제외")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    n, report = build(a.html, a.out, _parse_only(a.only) if a.only else None,
                      notes=not a.no_notes, verbose=not a.quiet)
    return 1 if report else 0


if __name__ == "__main__":
    sys.exit(main())
