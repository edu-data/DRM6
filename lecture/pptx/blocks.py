# -*- coding: utf-8 -*-
"""블록 단위 측정(measure)과 그리기(draw).

측정과 그리기는 같은 헬퍼를 쓰므로 항상 일치한다. 슬라이드 조립기는
먼저 measure() 로 전체 높이를 재고, 넘치면 배율 s 를 낮춰 다시 재는
식으로 넘침 없는 판면을 만든다.
"""

import os

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

import theme as T

FIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
FIG_CAP = 3.35          # 도해 한 컷의 최대 높이(inch)
MONO_LH = 1.22          # 모노스페이스 단락은 줄간을 좁게 (개요·코드 블록)


# ─── 저수준 헬퍼 ───────────────────────────────────────────────────────
def _emu(v):
    return Emu(int(round(v * 914400)))


def set_font(run, size, color, bold=False, mono=False):
    """라틴/동아시아 서체를 함께 지정한다 (python-pptx 는 ea 를 노출하지 않는다)."""
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    f.name = T.MONO_LATIN if mono else T.SANS_LATIN
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.insert_element_before(el, "a:sym", "a:hlinkClick",
                                      "a:hlinkMouseOver", "a:rtl", "a:extLst")
        el.set("typeface", T.MONO_EA if mono else T.SANS_EA)


def textbox(shapes, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    box = shapes.add_textbox(_emu(x), _emu(y), _emu(w), _emu(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    return tf


def rect(shapes, x, y, w, h, fill=None, line=None, line_w=0.75):
    sh = shapes.add_shape(MSO_SHAPE.RECTANGLE, _emu(x), _emu(y), _emu(w), _emu(h))
    sh.shadow.inherit = False
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(line_w)
    sh.text_frame.word_wrap = True
    return sh


def _style_of(st, base_color):
    """파서가 만든 서식 딕셔너리 → (색, 굵기, 모노)."""
    if st.get("accent"):
        return T.MAG, True, st.get("mono", False)
    if st.get("muted"):
        return T.INK_3, st.get("b", False), st.get("mono", False)
    if st.get("b"):
        return T.INK, True, st.get("mono", False)
    return base_color, False, st.get("mono", False)


def put_runs(tf, runs, size, color, line_h=T.LINE_H, space_after=0,
             align=PP_ALIGN.LEFT, mono=False, first=None):
    """파싱된 런 목록을 텍스트 프레임에 쓴다. '\\n' 은 문단을 나눈다."""
    paras = [[]]
    for text, st in runs:
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if i:
                paras.append([])
            if part:
                paras[-1].append((part, st))
    # 가운데 빈 줄은 살린다 — 측정은 빈 줄을 세므로 그리기도 그래야 하고,
    # 개요·예시 블록에서는 빈 줄 자체가 의미를 갖는다. 앞뒤 빈 줄만 버린다.
    while paras and not paras[0]:
        paras.pop(0)
    while paras and not paras[-1]:
        paras.pop()
    if not paras:
        paras = [[]]

    p = first if first is not None else tf.paragraphs[0]
    for i, para in enumerate(paras):
        if i:
            p = tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_h
        p.space_before = Pt(0)
        p.space_after = Pt(space_after if i == len(paras) - 1 else space_after * 0.5)
        if not para:                       # 빈 줄도 한 줄 높이를 차지해야 한다
            r = p.add_run()
            r.text = " "
            set_font(r, size, color, mono=mono)
            continue
        for text, st in para:
            c, b, m = _style_of(st, color)
            r = p.add_run()
            r.text = text
            set_font(r, size, c, bold=b, mono=mono or m)
    return p


def plain(runs):
    return "".join(t for t, _ in runs)


# ─── 열 폭 계산 ────────────────────────────────────────────────────────
def col_widths(total, ratio_key):
    ratios = T.GRID_RATIOS[ratio_key]
    n = len(ratios)
    avail = total - T.COL_GAP * (n - 1)
    unit = avail / sum(ratios)
    return [r * unit for r in ratios]


def table_col_widths(block, total):
    """열 내용의 최대 폭에 비례해 배분하되, 한쪽으로 쏠리지 않게 눌러준다."""
    rows = block["head"] + block["rows"]
    ncols = max((sum(c["span"] for c in r) for r in rows), default=1)
    weights = [1.0] * ncols
    for r in rows:
        i = 0
        for c in r:
            if c["span"] == 1 and i < ncols:
                mono = any(st.get("mono") for _, st in c["runs"])
                w = T.em_width(plain(c["runs"]).replace("\n", " "), mono)
                weights[i] = max(weights[i], min(w, 26.0))
            i += c["span"]
    weights = [max(w, 3.0) ** 0.72 for w in weights]      # 폭 차이를 완만하게
    unit = total / sum(weights)
    return [w * unit for w in weights]


# ─── 측정 ──────────────────────────────────────────────────────────────
def measure(b, w, s=1.0, fs=None):
    """s = 글자 배율, fs = 도해 배율(생략하면 s 와 같음).

    도해와 글자를 따로 줄일 수 있어야 한다. 판면이 넘칠 때 먼저 줄여야 할
    것은 읽어야 하는 글자가 아니라 그림이기 때문이다.
    """
    fs = s if fs is None else fs
    t = b["t"]
    if t == "para":
        mono = b.get("mono", False)
        size = T.FS["small" if mono else "body"] * s
        return T.text_height(plain(b["runs"]), size, w,
                             MONO_LH if mono else T.LINE_H, mono=mono)
    if t == "head":
        return T.FS["h4"] * s * 1.30 / 72.0
    if t == "list":
        size = T.FS["body"] * s
        ind = 0.16
        h = 0.0
        for it in b["items"]:
            h += T.text_height(plain(it), size, w - ind) + 0.028
        return h
    if t == "chips":
        return 0.235 * s + 0.04
    if t == "fig":
        cap = (T.FS["caption"] * s * 1.5 / 72.0) if b.get("caption") else 0.0
        inner = w - 2 * T.PAD_X
        return min(inner / b["aspect"], FIG_CAP) * fs + 2 * T.PAD_Y + cap
    if t == "card":
        inner = w - 2 * T.PAD_X
        h = 2 * T.PAD_Y
        if b["head"]:
            h += T.text_height(b["head"], T.FS["h4"] * s, inner - (0.5 if b["tag"] else 0)) + 0.055
        h += _stack_h(b["blocks"], inner, s, fs)
        return h
    if t == "call":
        inner = w - 2 * T.PAD_X
        h = 2 * T.PAD_Y
        if b["label"]:
            h += T.FS["label"] * s * 1.5 / 72.0
        h += _stack_h(b["blocks"], inner, s, fs)
        return h
    if t == "table":
        return _table_h(b, w, s)
    if t == "ba":
        half = (w - 0.02) / 2 - 2 * T.PAD_X
        best = 0.0
        for side in b["sides"]:
            h = 2 * T.PAD_Y + T.FS["label"] * s * 1.5 / 72.0
            for p in side["paras"]:
                h += _ba_para_h(p, s, half) + 0.08
            best = max(best, h)
        return best
    if t == "grid":
        ws = col_widths(w, b["ratio"])
        return max((_stack_h(col, cw, s, fs) for col, cw in zip(b["cols"], ws)),
                   default=0.0)
    return 0.0


def _stack_h(blocks, w, s, fs=None):
    if not blocks:
        return 0.0
    return sum(measure(x, w, s, fs) for x in blocks) + T.GAP * s * (len(blocks) - 1)


def _table_h(b, w, s):
    widths = table_col_widths(b, w)
    hs = _table_row_heights(b, widths, s)
    cap = (T.FS["caption"] * s * 1.5 / 72.0) if b.get("caption") else 0.0
    return sum(hs) + cap


def _table_row_heights(b, widths, s):
    out = []
    for is_head, row in ([(True, r) for r in b["head"]] + [(False, r) for r in b["rows"]]):
        size = T.FS["table_head" if is_head else "table"] * s
        hmax = 0.0
        i = 0
        for c in row:
            cw = sum(widths[i:i + c["span"]]) - 0.16
            i += c["span"]
            mono = any(st.get("mono") for _, st in c["runs"])
            hmax = max(hmax, T.text_height(plain(c["runs"]), size, max(cw, 0.4),
                                           1.28, mono=mono))
        out.append(hmax + 0.17 * s)
    return out


# ─── 그리기 ────────────────────────────────────────────────────────────
def draw(shapes, b, x, y, w, s=1.0, fs=None):
    """블록을 그리고 실제로 차지한 높이를 돌려준다."""
    return _DRAW[b["t"]](shapes, b, x, y, w, s, s if fs is None else fs)


def _stack(shapes, blocks, x, y, w, s, fs=None):
    cy = y
    for i, blk in enumerate(blocks):
        cy += draw(shapes, blk, x, cy, w, s, fs)
        if i != len(blocks) - 1:
            cy += T.GAP * s
    return cy - y


def _d_para(shapes, b, x, y, w, s, fs=None):
    mono = b.get("mono", False)
    size = T.FS["small" if mono else "body"] * s
    h = measure(b, w, s)
    tf = textbox(shapes, x, y, w, h + 0.05)
    put_runs(tf, b["runs"], size, T.INK_2, mono=mono,
             line_h=MONO_LH if mono else T.LINE_H)
    return h


def _d_head(shapes, b, x, y, w, s, fs=None):
    h = measure(b, w, s)
    tf = textbox(shapes, x, y, w, h + 0.05)
    put_runs(tf, b["runs"], T.FS["h4"] * s, T.HULL, line_h=1.25)
    return h


def _d_list(shapes, b, x, y, w, s, fs=None):
    size = T.FS["body"] * s
    ind = 0.16
    cy = y
    for i, item in enumerate(b["items"]):
        ih = T.text_height(plain(item), size, w - ind)
        mark = "%d." % (i + 1) if b["ordered"] else "◆"
        mtf = textbox(shapes, x, y=cy, w=ind, h=ih + 0.04)
        mp = mtf.paragraphs[0]
        mp.line_spacing = T.LINE_H
        r = mp.add_run()
        r.text = mark
        set_font(r, size * (0.78 if not b["ordered"] else 0.92), T.MAG,
                 bold=b["ordered"], mono=b["ordered"])
        tf = textbox(shapes, x + ind, cy, w - ind, ih + 0.04)
        put_runs(tf, item, size, T.INK_2)
        cy += ih + 0.028
    return cy - y


def _d_chips(shapes, b, x, y, w, s, fs=None):
    h = 0.235 * s
    cx = x
    for text, is_mag in b["items"]:
        cw = T.em_width(text, True) * T.FS["chip"] * s / 72.0 + 0.22
        if cx + cw > x + w and cx > x:
            break
        sh = rect(shapes, cx, y, cw, h, None, T.MAG if is_mag else T.RULE_2, 0.75)
        tf = sh.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = text
        set_font(r, T.FS["chip"] * s, T.MAG if is_mag else T.INK_2, mono=True)
        cx += cw + 0.08
    return h + 0.04


def _d_fig(shapes, b, x, y, w, s, fs=None):
    fs = s if fs is None else fs
    total = measure(b, w, s, fs)
    cap_h = (T.FS["caption"] * s * 1.5 / 72.0) if b.get("caption") else 0.0
    box_h = total - cap_h
    rect(shapes, x, y, w, box_h, T.PAPER_2, T.RULE, 0.75)
    path = os.path.join(FIG_DIR, "fig-%02d.png" % b["index"])
    inner_w = w - 2 * T.PAD_X
    img_h = box_h - 2 * T.PAD_Y
    img_w = min(inner_w, img_h * b["aspect"])
    img_h = img_w / b["aspect"]
    if os.path.exists(path):
        shapes.add_picture(path, _emu(x + (w - img_w) / 2),
                           _emu(y + (box_h - img_h) / 2), _emu(img_w), _emu(img_h))
    else:                                    # PNG 가 없으면 대체 표시
        tf = textbox(shapes, x + T.PAD_X, y + box_h / 2 - 0.12, inner_w, 0.3)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = "[도해] " + (b["alt"] or "figures/fig-%02d.png 없음" % b["index"])
        set_font(r, T.FS["caption"] * s, T.INK_3, mono=True)
    if cap_h:
        tf = textbox(shapes, x, y + box_h + 0.03, w, cap_h)
        p = tf.paragraphs[0]
        r = p.add_run()
        r.text = b["caption"]
        set_font(r, T.FS["caption"] * s, T.INK_3, mono=True)
    return total


def _d_card(shapes, b, x, y, w, s, fs=None):
    fs = s if fs is None else fs
    h = measure(b, w, s, fs)
    key = b["variant"] == "key"
    rect(shapes, x, y, w, h, T.MAG_SOFT if key else T.PAPER_2,
         T.MAG if key else T.RULE, 0.75)
    inner = w - 2 * T.PAD_X
    cy = y + T.PAD_Y
    if b["tag"]:                              # 우상단 배지
        tw = max(T.em_width(b["tag"], True) * T.FS["chip"] * s / 72.0 + 0.16, 0.30)
        sh = rect(shapes, x + w - tw, y, tw, 0.20 * s + 0.03, T.HULL, None)
        tf = sh.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = b["tag"]
        set_font(r, T.FS["chip"] * s, T.PAPER, mono=True)
    if b["head"]:
        hw = inner - (0.55 if b["tag"] else 0)
        hh = T.text_height(b["head"], T.FS["h4"] * s, hw)
        tf = textbox(shapes, x + T.PAD_X, cy, hw, hh + 0.05)
        p = tf.paragraphs[0]
        p.line_spacing = 1.25
        r = p.add_run()
        r.text = b["head"]
        set_font(r, T.FS["h4"] * s, T.MAG if key else T.HULL, bold=True)
        cy += hh + 0.055
    _stack(shapes, b["blocks"], x + T.PAD_X, cy, inner, s, fs)
    return h


def _d_call(shapes, b, x, y, w, s, fs=None):
    fs = s if fs is None else fs
    h = measure(b, w, s, fs)
    color, bg = T.CALL_KINDS[b["kind"]]
    rect(shapes, x, y, w, h, bg, T.RULE_2 if b["kind"] == "def" else color, 0.75)
    inner = w - 2 * T.PAD_X
    cy = y + T.PAD_Y
    if b["label"]:
        lh = T.FS["label"] * s * 1.5 / 72.0
        tf = textbox(shapes, x + T.PAD_X, cy, inner, lh)
        p = tf.paragraphs[0]
        r = p.add_run()
        r.text = b["label"]
        set_font(r, T.FS["label"] * s, color, bold=True, mono=True)
        cy += lh
    _stack(shapes, b["blocks"], x + T.PAD_X, cy, inner, s, fs)
    return h


def _d_ba(shapes, b, x, y, w, s, fs=None):
    h = measure(b, w, s)
    half = (w - 0.02) / 2
    for i, side in enumerate(b["sides"]):
        bg = T.CRIT_BG if i == 0 else T.GOOD_BG
        fg = T.CRIT if i == 0 else T.GOOD
        sx = x + i * (half + 0.02)
        rect(shapes, sx, y, half, h, bg, T.RULE, 0.75)
        inner = half - 2 * T.PAD_X
        cy = y + T.PAD_Y
        lh = T.FS["label"] * s * 1.5 / 72.0
        tf = textbox(shapes, sx + T.PAD_X, cy, inner, lh)
        r = tf.paragraphs[0].add_run()
        r.text = side["label"]
        set_font(r, T.FS["label"] * s, fg, bold=True, mono=True)
        cy += lh
        for para in side["paras"]:
            ph = _ba_para_h(para, s, inner)
            tf = textbox(shapes, sx + T.PAD_X, cy, inner, ph)
            put_runs(tf, para, T.FS["body"] * s, T.INK_2)
            cy += ph + 0.08
    return h


def _ba_para_h(para, s, width):
    """before/after 상자의 단락 높이 — 측정과 그리기가 같은 값을 쓴다."""
    return T.text_height(plain(para), T.FS["body"] * s, width, T.LINE_H * 1.10)


def _d_table(shapes, b, x, y, w, s, fs=None):
    widths = table_col_widths(b, w)
    heights = _table_row_heights(b, widths, s)
    rows = [(True, r) for r in b["head"]] + [(False, r) for r in b["rows"]]
    ncols = len(widths)
    gf = shapes.add_table(len(rows), ncols, _emu(x), _emu(y), _emu(w),
                          _emu(sum(heights)))
    tbl = gf.table
    tblPr = tbl._tbl.tblPr
    for e in tblPr.findall(qn("a:tableStyleId")):
        tblPr.remove(e)
    tblPr.set("firstRow", "0")
    tblPr.set("bandRow", "0")
    for i, cw in enumerate(widths):
        tbl.columns[i].width = _emu(cw)
    for i, hh in enumerate(heights):
        tbl.rows[i].height = _emu(hh)

    for ri, (is_head, row) in enumerate(rows):
        ci = 0
        for cell_data in row:
            span = cell_data["span"]
            cell = tbl.cell(ri, ci)
            if span > 1 and ci + span - 1 < ncols:
                cell.merge(tbl.cell(ri, ci + span - 1))
            cell.margin_left = cell.margin_right = _emu(0.08)
            cell.margin_top = cell.margin_bottom = _emu(0.035)
            cell.vertical_anchor = MSO_ANCHOR.TOP
            cell.fill.solid()
            if is_head:
                cell.fill.fore_color.rgb = T.HULL
                base, size, bold = T.PAPER, T.FS["table_head"] * s, True
            else:
                cell.fill.fore_color.rgb = T.ROW_ALT if ri % 2 else T.PAPER_2
                first_col = ci == 0 and span == 1
                base = T.INK if first_col else T.INK_2
                size, bold = T.FS["table"] * s, first_col
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.line_spacing = 1.28
            for text, st in _flatten(cell_data["runs"]):
                c, bb, mm = _style_of(st, base)
                if is_head:
                    c = T.PAPER
                r = p.add_run()
                r.text = text
                set_font(r, size, c, bold=bold or bb, mono=mm)
            ci += span
    cap_h = 0.0
    if b.get("caption"):
        cap_h = T.FS["caption"] * s * 1.5 / 72.0
        tf = textbox(shapes, x, y + sum(heights) + 0.03, w, cap_h)
        r = tf.paragraphs[0].add_run()
        r.text = b["caption"]
        set_font(r, T.FS["caption"] * s, T.INK_3, mono=True)
    return sum(heights) + cap_h


def _flatten(runs):
    """표 칸에서는 줄바꿈을 공백으로 눌러 한 문단으로 만든다."""
    return [(t.replace("\n", " "), st) for t, st in runs]


def _d_grid(shapes, b, x, y, w, s, fs=None):
    ws = col_widths(w, b["ratio"])
    cx, tallest = x, 0.0
    for col, cw in zip(b["cols"], ws):
        tallest = max(tallest, _stack(shapes, col, cx, y, cw, s, fs))
        cx += cw + T.COL_GAP
    return tallest


_DRAW = {"para": _d_para, "head": _d_head, "list": _d_list, "chips": _d_chips,
         "fig": _d_fig, "card": _d_card, "call": _d_call, "ba": _d_ba,
         "table": _d_table, "grid": _d_grid}
