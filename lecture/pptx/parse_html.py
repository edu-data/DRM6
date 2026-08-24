# -*- coding: utf-8 -*-
"""lecture/index.html 을 슬라이드 데이터로 변환한다.

강의자료 HTML 은 정해진 클래스 어휘(.card/.call/.tbl/.ba/.fig/.g2…)로만
작성되어 있으므로, 그 어휘만 이해하는 작은 파서로 안전하게 읽을 수 있다.
HTML 이 단일 원본이고 PPTX 는 거기서 파생된다.
"""

import re
from html.parser import HTMLParser

VOID = {"br", "hr", "img", "meta", "link", "input", "col", "source"}
GRID_CLASSES = {"g2", "g3", "g4", "g21", "g12"}
BLOCK_CLASSES = {"card", "call", "tw", "ba", "fig", "chips"}


# ─── 최소 DOM ──────────────────────────────────────────────────────────
class Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag, attrs=None):
        self.tag, self.attrs, self.children = tag, attrs or {}, []

    @property
    def cls(self):
        return set(self.attrs.get("class", "").split())

    def kids(self):
        return [c for c in self.children if isinstance(c, Node)]

    def find(self, tag=None, cls=None):
        for n in self.walk():
            if (tag is None or n.tag == tag) and (cls is None or cls in n.cls):
                return n
        return None

    def walk(self):
        for c in self.kids():
            yield c
            yield from c.walk()


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, dict(attrs))
        self.stack[-1].children.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_document(path):
    src = open(path, encoding="utf-8").read()
    src = re.sub(r"<script\b.*?</script>", "", src, flags=re.S)
    src = re.sub(r"<style\b.*?</style>", "", src, flags=re.S)
    b = _Builder()
    b.feed(src)
    return b.root


# ─── 인라인 서식 → 런(run) 목록 ────────────────────────────────────────
def runs_of(node, base=None):
    """(텍스트, 서식) 튜플 목록. 서식 키: b, accent, mono, muted."""
    base = dict(base or {})
    out = []
    for c in node.children:
        if isinstance(c, str):
            if c:
                out.append((c, dict(base)))
            continue
        if c.tag == "br":
            out.append(("\n", dict(base)))
            continue
        if c.tag == "svg":
            continue
        st = dict(base)
        if c.tag in ("b", "strong"):
            st["b"] = True
        elif c.tag == "em":
            st["b"] = True
            st["accent"] = True
        elif c.tag == "code":
            st["mono"] = True
        if "mono" in c.cls:
            st["mono"] = True
        if "chip" in c.cls:
            st["mono"] = True
        style = c.attrs.get("style", "")
        m = re.search(r"color:\s*var\(--([a-z0-9-]+)\)", style)
        if m:
            var = m.group(1)
            if var.startswith("mag"):
                st["accent"] = True
            elif var.startswith("ink-3"):
                st["muted"] = True
        out.extend(runs_of(c, st))
    return _tidy(out)


def _tidy(runs):
    """공백 정리 후 같은 서식의 인접 런을 합친다."""
    merged = []
    for text, st in runs:
        text = re.sub(r"[ \t\r]*\n[ \t\r]*", "\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        if not text:
            continue
        if merged and merged[-1][1] == st:
            merged[-1][0] += text
        else:
            merged.append([text, st])
    if merged:
        merged[0][0] = merged[0][0].lstrip()
        merged[-1][0] = merged[-1][0].rstrip()
    return [(t, s) for t, s in merged if t]


def plain(runs):
    return "".join(t for t, _ in runs)


# ─── 블록 ──────────────────────────────────────────────────────────────
class _FigCounter:
    """문서 전체에서 .fig 가 나타나는 순서 = 미리 렌더한 PNG 의 번호."""

    def __init__(self):
        self.n = -1

    def next(self):
        self.n += 1
        return self.n


def _as_blocks(node, fc):
    """열(column) 하나를 블록 목록으로. 노드 자체가 블록이면 그것 하나."""
    if node.cls & BLOCK_CLASSES or node.cls & GRID_CLASSES:
        return _blocks_from([node], fc)
    return _blocks_from(node.kids(), fc)


def _blocks_from(nodes, fc):
    out = []
    for c in nodes:
        cl = c.cls
        if "figcap" in cl:                       # 앞선 도해/표의 캡션
            if out and out[-1]["t"] in ("fig", "table"):
                out[-1]["caption"] = plain(runs_of(c))
            continue
        if "card" in cl:
            out.append(_card(c, fc))
        elif "call" in cl:
            out.append(_call(c, fc))
        elif "tw" in cl:
            out.append(_table(c))
        elif "ba" in cl:
            out.append(_ba(c))
        elif "fig" in cl:
            out.append({"t": "fig", "index": fc.next(),
                        "alt": (c.find("svg").attrs.get("aria-label", "")
                                if c.find("svg") is not None else ""),
                        "aspect": _aspect(c), "caption": None})
        elif cl & GRID_CLASSES:
            out.append(_grid(c, fc))
        elif "row" in cl and c.find(cls="chip") is not None:
            out.append({"t": "chips",
                        "items": [(plain(runs_of(k)), "m" in k.cls)
                                  for k in c.kids() if "chip" in k.cls]})
        elif "stack" in cl:
            out.extend(_blocks_from(c.kids(), fc))
        elif c.tag == "p":
            r = runs_of(c)
            if r:
                out.append({"t": "para", "runs": r,
                            "mono": "mono" in cl, "small": "q" not in cl and "mono" in cl})
        elif c.tag in ("ul", "ol"):
            out.append({"t": "list", "ordered": c.tag == "ol",
                        "items": [runs_of(li) for li in c.kids() if li.tag == "li"]})
        elif c.tag in ("h4", "h3"):
            out.append({"t": "head", "runs": runs_of(c)})
        elif c.tag == "div":
            out.extend(_blocks_from(c.kids(), fc))
    return out


def _aspect(fignode):
    svg = fignode.find("svg")
    if svg is None:
        return 2.0
    vb = svg.attrs.get("viewBox", "0 0 4 3").split()
    try:
        return float(vb[2]) / float(vb[3])
    except (ValueError, ZeroDivisionError, IndexError):
        return 2.0


def _grid(node, fc):
    ratio_key = next(iter(node.cls & GRID_CLASSES))
    return {"t": "grid", "ratio": ratio_key,
            "cols": [_as_blocks(k, fc) for k in node.kids()]}


def _card(node, fc):
    tag = node.find(cls="tag")
    head = node.find("h4")
    body_nodes = [k for k in node.kids() if k is not tag and k is not head]
    return {"t": "card",
            "variant": "key" if "key" in node.cls else "plain",
            "tag": plain(runs_of(tag)) if tag is not None else None,
            "head": plain(runs_of(head)) if head is not None else None,
            "blocks": _blocks_from(body_nodes, fc)}


def _call(node, fc):
    kind = next((k for k in ("def", "warn", "case", "do") if k in node.cls), "def")
    kids = node.kids()
    label, rest = None, list(node.children)
    if kids and kids[0].tag == "b":
        label = plain(runs_of(kids[0]))
        rest = [c for c in node.children if c is not kids[0]]
    holder = Node("div")
    holder.children = rest
    inline, blocks = [], []
    for c in holder.children:                    # 콜아웃은 인라인과 블록이 섞인다
        if isinstance(c, str) or (c.tag not in ("ul", "ol", "div", "p", "table")
                                  and not (c.cls & BLOCK_CLASSES)):
            inline.append(c)
        else:
            if inline:
                h = Node("p")
                h.children = inline
                blocks.append({"t": "para", "runs": runs_of(h), "mono": False, "small": False})
                inline = []
            blocks.extend(_blocks_from([c], fc))
    if inline:
        h = Node("p")
        h.children = inline
        r = runs_of(h)
        if r:
            blocks.append({"t": "para", "runs": r, "mono": False, "small": False})
    return {"t": "call", "kind": kind, "label": label,
            "blocks": [b for b in blocks if b.get("runs") or b["t"] != "para"]}


def _table(node):
    tbl = node.find("table")
    head, rows = [], []
    for tr in [n for n in tbl.walk() if n.tag == "tr"]:
        cells = [c for c in tr.kids() if c.tag in ("th", "td")]
        row = [{"runs": runs_of(c),
                "span": int(c.attrs.get("colspan", 1)),
                "th": c.tag == "th"} for c in cells]
        (head if all(c["th"] for c in row) else rows).append(row)
    return {"t": "table", "head": head, "rows": rows, "caption": None}


def _ba(node):
    sides = node.kids()[:2]
    out = []
    for s in sides:
        b = s.find("b")
        label = plain(runs_of(b)) if b is not None else ""
        paras = [runs_of(p) for p in s.kids() if p.tag == "p"]
        out.append({"label": label, "paras": [p for p in paras if p]})
    return {"t": "ba", "sides": out}


# ─── 슬라이드 ──────────────────────────────────────────────────────────
def parse_slides(path):
    root = parse_document(path)
    fc = _FigCounter()
    out = []
    for sec in root.walk():
        if sec.tag != "section" or "slide" not in sec.cls:
            continue
        cl = sec.cls
        note = sec.find(cls="note")
        data = {"part": sec.attrs.get("data-part", "0"),
                "title": sec.attrs.get("data-title", ""),
                "note": _note_text(note)}
        if "cover" in cl:
            data.update(kind="cover", **_cover(sec))
        elif "part" in cl:
            data.update(kind="part", **_part(sec))
        else:
            data.update(kind="content", **_content(sec, fc))
        out.append(data)
    return out


def _note_text(node):
    if node is None:
        return ""
    kids = node.kids()
    if kids and kids[0].tag == "b":
        rest = Node("div")
        rest.children = [c for c in node.children if c is not kids[0]]
        return plain(runs_of(rest))
    return plain(runs_of(node))


def _cover(sec):
    meta = sec.find(cls="meta")
    return {"kicker": plain(runs_of(sec.find(cls="kicker"))),
            "h1": _cover_h1(sec.find("h1")),
            "sub": plain(runs_of(sec.find(cls="sub"))),
            "meta": [(plain(runs_of(d.find("b"))),
                      plain(runs_of(d.find("span"))))
                     for d in (meta.kids() if meta else [])]}


def _cover_h1(h1):
    """표지 제목의 <span> 은 CSS(.cover h1 span)로만 강조색이 지정돼 있다."""
    out = []
    for c in h1.children:
        if isinstance(c, str):
            out.append((c, {}))
        elif c.tag == "br":
            out.append(("\n", {}))
        elif c.tag == "span":
            out.extend((t, dict(st, accent=True)) for t, st in runs_of(c))
        else:
            out.extend(runs_of(c))
    return _tidy(out)


def _part(sec):
    pq = sec.find(cls="pq")
    return {"pno": plain(runs_of(sec.find(cls="pno"))),
            "h2": plain(runs_of(sec.find("h2"))),
            "pen": plain(runs_of(sec.find(cls="pen"))),
            "lead": plain(runs_of(sec.find(cls="pl"))),
            "chips": [plain(runs_of(k)) for k in (pq.kids() if pq else [])]}


def _content(sec, fc):
    eyebrow = sec.find(cls="eyebrow")
    h2 = sec.find("h2")
    lead = sec.find(cls="lead")
    blocks = []
    for body in [n for n in sec.walk() if "body" in n.cls]:
        if body.cls & GRID_CLASSES:
            blocks.append(_grid(body, fc))
        else:
            blocks.extend(_blocks_from(body.kids(), fc))
    return {"eyebrow": plain(runs_of(eyebrow)) if eyebrow is not None else "",
            "h2": runs_of(h2) if h2 is not None else [],
            "lead": runs_of(lead) if lead is not None else [],
            "blocks": blocks}
