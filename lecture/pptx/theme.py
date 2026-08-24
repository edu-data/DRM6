# -*- coding: utf-8 -*-
"""해도(海圖) 제도 디자인 토큰.

lecture/index.html 의 CSS 커스텀 속성과 같은 값을 사용한다.
슬라이드는 인쇄·투사를 전제로 라이트 팔레트 하나에 고정한다.
"""

import re

from pptx.dml.color import RGBColor
from pptx.util import Emu, Inches


# ─── 색 ────────────────────────────────────────────────────────────────
def rgb(h):
    return RGBColor.from_string(h.upper())


def blend(fg, bg, alpha):
    """반투명 색을 불투명 색으로 환산한다 (PPTX 도형 채우기는 단색이 안전하다)."""
    f, b = rgb(fg), rgb(bg)
    return RGBColor(*(round(f[i] * alpha + b[i] * (1 - alpha)) for i in range(3)))


PAPER    = rgb("EDF1F3")   # 해도 지면
PAPER_2  = rgb("E4EBED")   # 카드 바탕
PAPER_3  = rgb("D5E0E3")
PAPER_4  = rgb("C6D5D9")
INK      = rgb("0B1F2A")   # 본문
INK_2    = rgb("3A5763")   # 부속 본문
INK_3    = rgb("6B8792")   # 캡션·수심 주기
HULL     = rgb("12384E")   # 선체 남색 — 표 머리글, 카드 제목
MAG      = rgb("B5177E")   # 해도 오버프린트 마젠타 — 유일한 강조색
GOOD     = rgb("166B4E")
WARN     = rgb("9A5A08")
CRIT     = rgb("A01B26")

MAG_SOFT = blend("B5177E", "E4EBED", 0.09)
GOOD_BG  = blend("166B4E", "E4EBED", 0.11)
WARN_BG  = blend("9A5A08", "E4EBED", 0.11)
CRIT_BG  = blend("A01B26", "E4EBED", 0.10)
RULE     = blend("0B1F2A", "EDF1F3", 0.16)
RULE_2   = blend("0B1F2A", "EDF1F3", 0.32)
ROW_ALT  = blend("0B1F2A", "E4EBED", 0.045)

# 콜아웃 종류별 (라벨색, 바탕색)
CALL_KINDS = {
    "def":  (HULL, PAPER_2),
    "warn": (WARN, WARN_BG),
    "case": (MAG,  MAG_SOFT),
    "do":   (GOOD, GOOD_BG),
}


# ─── 글꼴 ──────────────────────────────────────────────────────────────
# latin 은 Office 기본 탑재 서체, ea(동아시아) 는 한글 서체를 따로 지정한다.
# python-pptx 는 ea 를 노출하지 않으므로 render.set_font() 가 XML 로 직접 쓴다.
SANS_LATIN = "Arial"
SANS_EA    = "맑은 고딕"
MONO_LATIN = "Courier New"
MONO_EA    = "맑은 고딕"


# ─── 판면 (13.333 × 7.5 in, 16:9) ──────────────────────────────────────
SLIDE_W, SLIDE_H = 13.333, 7.5

MARGIN_L  = 1.02          # 본문 왼쪽 — 항정선 레일 오른쪽
MARGIN_R  = 0.62
MARGIN_T  = 0.44
RAIL_X    = 0.60          # 항정선 x 좌표
CHROME_Y  = 6.98          # 하단 진행바
BODY_BOT  = 6.72          # 본문이 넘어서면 안 되는 하한

CONTENT_W = SLIDE_W - MARGIN_L - MARGIN_R
GAP       = 0.17          # 블록 사이 기본 간격
COL_GAP   = 0.20          # 열 사이 간격
PAD_X     = 0.15          # 카드 안쪽 좌우 여백
PAD_Y     = 0.11          # 카드 안쪽 상하 여백


# ─── 글자 크기 (pt) ────────────────────────────────────────────────────
FS = {
    "cover_kicker": 11.5, "cover_h1": 44, "cover_sub": 15, "cover_meta": 11,
    "part_no": 54, "part_h": 38, "part_en": 11.5, "part_lead": 13,
    "eyebrow": 10, "title": 27, "lead": 12.5,
    "h4": 12, "body": 10.5, "small": 9.5,
    "table_head": 9.5, "table": 9,
    "chip": 8.5, "label": 8.5, "caption": 8.5, "chrome": 8.5,
}

LINE_H = 1.36             # 한글 본문 줄간
GRID_RATIOS = {           # HTML 의 .g* 클래스 → 열 비율
    "g2": (1, 1), "g3": (1, 1, 1), "g4": (1, 1, 1, 1),
    "g21": (1.35, 1), "g12": (1, 1.5),
}


# ─── 텍스트 실측 근사 ──────────────────────────────────────────────────
_NARROW = set("iljtfrI().,:;'\"|![]{}·")
_TOKEN = re.compile(r"\S+\s*")


MONO_LATIN_EM = 0.60      # Courier New 고정폭
MONO_WIDE_EM = 1.00       # 고정폭 서체에서 한글은 두 칸


def _is_wide(ch):
    o = ord(ch)
    return (0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F
            or 0x4E00 <= o <= 0x9FFF or 0xFF01 <= o <= 0xFF60
            or o in (0x2192, 0x2190, 0x00B7, 0x2014, 0x2015))


def em_width(s, mono=False):
    """문자열의 폭을 em 단위로 근사한다.

    고정폭 서체는 모든 라틴 글자가 같은 폭이므로 비례폰트 가중치를 쓰면
    폭을 크게 낮춰 잡게 된다. mono=True 로 따로 계산한다.
    """
    if mono:
        return sum(MONO_WIDE_EM if _is_wide(c) else MONO_LATIN_EM for c in s)
    w = 0.0
    for ch in s:
        if _is_wide(ch):
            w += 1.0
        elif ch == " ":
            w += 0.28
        elif ch in _NARROW:
            w += 0.30
        elif ch.isdigit():
            w += 0.56
        elif ch.isupper():
            w += 0.68
        else:
            w += 0.53
    return w


def wrapped_lines(text, size_pt, width_in, slack=1.02, mono=False):
    """줄 수를 센다.

    단순히 총 글자폭을 나누면 실제보다 적게 나온다 — 어절이 다음 줄로
    밀리며 줄 끝에 빈 자리가 남기 때문이다. 그래서 파워포인트와 같은
    어절 단위 그리디 줄바꿈을 그대로 흉내 낸다.
    """
    if not text.strip():
        return 1
    per_line = (width_in * 72.0) / size_pt / slack      # em 단위 한 줄 용량
    if per_line <= 0:
        return 1
    total = 0
    for seg in text.split("\n"):
        tokens = _TOKEN.findall(seg)
        if not tokens:
            total += 1
            continue
        lines, cur = 1, 0.0
        for tk in tokens:
            full = em_width(tk, mono)
            bare = em_width(tk.rstrip(), mono)
            if full > per_line:                          # 한 어절이 한 줄보다 길면
                if cur > 0:
                    lines += 1
                lines += int(full // per_line)
                cur = full % per_line
            elif cur > 0 and cur + bare > per_line:
                lines += 1
                cur = full
            else:
                cur += full
        total += lines
    return total


def text_height(text, size_pt, width_in, line_h=LINE_H, mono=False):
    """줄바꿈을 고려한 텍스트 높이(inch)."""
    return wrapped_lines(text, size_pt, width_in, mono=mono) * size_pt * line_h / 72.0


def inches(v):
    return Inches(v)


def emu(v):
    return Emu(int(round(v * 914400)))
