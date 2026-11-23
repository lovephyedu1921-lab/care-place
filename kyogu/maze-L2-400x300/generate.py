#!/usr/bin/env python3
"""
브릿지케어 인지교구 · 길 찾기 미로판 2단계(경증) 400 x 300 x 18 mm
CNC 가공용 DXF, UV 인쇄용 SVG, 제작 도면 SVG, 미리보기 SVG를 생성한다.

필요 패키지: pip install ezdxf shapely fonttools
실행: python3 generate.py   (결과는 ./output 폴더)
"""
import math
import pathlib
from collections import deque

import ezdxf
from ezdxf import units
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely import affinity
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

# ─────────────────────────── 규격 (mm) ───────────────────────────
W, H, T = 400.0, 300.0, 18.0      # 판 크기 / 두께 (자작나무 합판 18T)
CORNER_R = 15.0                   # 판 모서리 R
GROOVE_W = 12.0                   # 홈 폭 (Ø10 목심 + 여유 2)
GROOVE_D = 8.0                    # 홈 깊이 (판 남는 두께 10)
LAND_R = 3.0                      # 홈 사이 나무 모서리 라운드 (손 다침 방지)
COLS, ROWS = 7, 5                 # 미로 격자
X0, X1 = 45.0, 355.0              # 첫/마지막 열 중심
Y0, Y1 = 45.0, 255.0              # 첫(출발)/마지막(도착) 행 중심 (아래→위)
BLOCK = 50.0                      # 블록 한 변
BLOCK_R = 8.0                     # 블록 모서리 R
PEG_D = 10.0                      # 목심 지름
PEG_HOLE = 10.0                   # 블록 목심 구멍 깊이
PEG_OUT = 6.0                     # 목심이 블록 밑으로 나오는 길이 (홈 깊이 8 → 바닥 여유 2)
FRAME_OUT, FRAME_IN = 60.0, 52.0  # 도착 표시 테두리 (블록 50 이 들어가면 테두리만 보임)
PRINT_CLEAR = 1.5                 # 인쇄를 홈 가장자리에서 떨어뜨리는 거리

PITCH_X = (X1 - X0) / (COLS - 1)
PITCH_Y = (Y1 - Y0) / (ROWS - 1)


def node(c, r):
    return (X0 + c * PITCH_X, Y0 + r * PITCH_Y)


# ─────────────────────────── 미로 설계 ───────────────────────────
# 행 r 의 가로 홈 (열 a ↔ 열 b)
H_EDGES = {
    1: [(0, 1), (1, 2), (2, 3), (4, 5), (5, 6)],
    2: [(0, 1), (1, 2), (2, 3), (3, 4), (5, 6)],   # (0,2) 는 막다른 길
    3: [(0, 1), (1, 2), (2, 3), (4, 5), (5, 6)],   # (3,3) 은 막다른 길
}
# 행 r → r+1 로 올라가는 세로 홈이 있는 열
V_EDGES = {
    0: [0, 2, 4, 6],   # 출발 4곳
    1: [1, 3, 5, 6],
    2: [2, 4, 6],
    3: [0, 2, 4, 6],   # 도착 4곳
}

COLORS = {
    "circle": "#D62828",    # 빨강
    "triangle": "#1D5FBF",  # 파랑
    "square": "#F4A300",    # 노랑(주황빛, 나무색 위에서 잘 보이도록)
    "star": "#2A9D4B",      # 초록
}
OUTLINE = "#2B2B2B"
NAMES = {"circle": "동그라미", "triangle": "세모", "square": "네모", "star": "별"}
STARTS = {0: "circle", 2: "triangle", 4: "square", 6: "star"}     # 아래 줄 (어르신 쪽)
TARGETS = {0: "triangle", 2: "circle", 4: "star", 6: "square"}    # 위 줄


def edges():
    for r, pairs in H_EDGES.items():
        for a, b in pairs:
            yield (a, r), (b, r)
    for r, cols in V_EDGES.items():
        for c in cols:
            yield (c, r), (c, r + 1)


def graph():
    g = {}
    for a, b in edges():
        g.setdefault(a, set()).add(b)
        g.setdefault(b, set()).add(a)
    return g


def solve(g, start, goal):
    prev = {start: None}
    q = deque([start])
    while q:
        n = q.popleft()
        if n == goal:
            break
        for m in sorted(g[n]):
            if m not in prev:
                prev[m] = n
                q.append(m)
    if goal not in prev:
        return None
    path, n = [], goal
    while n is not None:
        path.append(n)
        n = prev[n]
    return path[::-1]


def check_maze():
    g = graph()
    routes = {}
    for c, shape in STARTS.items():
        tc = [k for k, v in TARGETS.items() if v == shape][0]
        p = solve(g, (c, 0), (tc, ROWS - 1))
        assert p, f"{shape} 경로 없음"
        inner = p[1:-1]
        # 다른 출발/도착 칸(블록이 놓여 있는 칸)을 지나가지 않아야 함
        assert all(0 < r < ROWS - 1 for _, r in inner), f"{shape} 경로가 다른 블록 칸을 지나감"
        routes[shape] = p
    dead_ends = [n for n, nb in g.items() if len(nb) == 1 and 0 < n[1] < ROWS - 1]
    branches = [n for n, nb in g.items() if len(nb) >= 3]
    return g, routes, dead_ends, branches


# ─────────────────────────── 형상 ───────────────────────────
def rounded_rect(x, y, w, h, r):
    return box(x, y, x + w, y + h).buffer(-r, quad_segs=16).buffer(r, quad_segs=16)


def groove_geometry():
    segs = [LineString([node(*a), node(*b)]) for a, b in edges()]
    g = unary_union([s.buffer(GROOVE_W / 2, quad_segs=16) for s in segs])
    # 닫힘 연산: 홈이 만나는 곳의 뾰족한 나무 모서리를 R3 로 둥글게
    g = g.buffer(LAND_R, quad_segs=8).buffer(-LAND_R, quad_segs=8)
    return segs, g


def shape_poly(kind, cx, cy, size):
    """size: 외접 크기 (mm)"""
    s = size / 2
    if kind == "circle":
        return Point(cx, cy).buffer(s * 0.95, quad_segs=24)
    if kind == "square":
        return rounded_rect(cx - s * 0.85, cy - s * 0.85, s * 1.7, s * 1.7, 3)
    if kind == "triangle":
        r = s * 1.08
        pts = [(cx + r * math.cos(math.radians(90 + 120 * i)),
                cy - r * 0.18 + r * math.sin(math.radians(90 + 120 * i))) for i in range(3)]
        return Polygon(pts).buffer(-1.5, join_style=1).buffer(1.5, join_style=1)
    if kind == "star":
        pts = []
        for i in range(10):
            rr = s * 1.02 if i % 2 == 0 else s * 0.44
            a = math.radians(90 + 36 * i)
            pts.append((cx + rr * math.cos(a), cy - s * 0.04 + rr * math.sin(a)))
        return Polygon(pts).buffer(-0.8, join_style=1).buffer(0.8, join_style=1)
    raise ValueError(kind)


def shape_parts(kind, cx, cy, size, line=1.6):
    """(채움, 외곽선) 두 폴리곤"""
    p = shape_poly(kind, cx, cy, size)
    fill = p.buffer(-line, join_style=1)
    return fill, p.difference(fill)


# ─────────────────────────── 글자 → 외곽선 ───────────────────────────
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
_font = TTFont(FONT_PATH, fontNumber=0)
_gs = _font.getGlyphSet()
_cmap = _font.getBestCmap()
_upm = _font["head"].unitsPerEm
_hmtx = _font["hmtx"]


def text_outline_path(text, x, baseline, size, anchor="middle"):
    """SVG(y 아래 방향) 좌표의 외곽선 path d. size = 글자 높이(em, mm)"""
    sc = size / _upm
    names = [_cmap.get(ord(ch), ".notdef") for ch in text]
    total = sum(_hmtx[n][0] for n in names) * sc
    cx = x - total / 2 if anchor == "middle" else x
    pen = SVGPathPen(_gs)
    for n in names:
        tp = TransformPen(pen, (sc, 0, 0, -sc, cx, baseline))
        _gs[n].draw(tp)
        cx += _hmtx[n][0] * sc
    return pen.getCommands()


# ─────────────────────────── SVG 도우미 ───────────────────────────
def fy(y):
    return H - y   # 판 좌표(y 위로) → SVG(y 아래로)


def path_d(geom: BaseGeometry, tx=lambda x, y: (x, fy(y))):
    polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
    out = []
    for p in polys:
        if p.is_empty or p.geom_type != "Polygon":
            continue
        for ring in [p.exterior, *p.interiors]:
            pts = [tx(x, y) for x, y in ring.coords]
            out.append("M" + " L".join(f"{a:.3f},{b:.3f}" for a, b in pts) + " Z")
    return " ".join(out)


def svg_doc(w_mm, h_mm, body, extra_defs="", vb=None, bg=None):
    vb = vb or f"0 0 {w_mm} {h_mm}"
    bgrect = f'<rect x="0" y="0" width="{w_mm}" height="{h_mm}" fill="{bg}"/>' if bg else ""
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm}mm" height="{h_mm}mm" '
            f'viewBox="{vb}">\n<defs>{extra_defs}</defs>\n{bgrect}\n{body}\n</svg>\n')


# ─────────────────────────── DXF ───────────────────────────
BULGE_90 = math.tan(math.radians(90) / 4)


def add_rounded_rect_dxf(msp, x, y, w, h, r, layer):
    """원호(bulge)가 살아있는 둥근 사각형 – CNC 에서 매끈하게 가공됨"""
    pts = [
        (x + r, y, 0), (x + w - r, y, BULGE_90),
        (x + w, y + r, 0), (x + w, y + h - r, BULGE_90),
        (x + w - r, y + h, 0), (x + r, y + h, BULGE_90),
        (x, y + h - r, 0), (x, y + r, BULGE_90),
    ]
    msp.add_lwpolyline(pts, format="xyb", close=True, dxfattribs={"layer": layer})


def add_poly_dxf(msp, geom, layer):
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            msp.add_lwpolyline(list(ring.coords)[:-1], close=True, dxfattribs={"layer": layer})


def new_dxf(layers):
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.MM
    doc.header["$MEASUREMENT"] = 1
    doc.header["$INSUNITS"] = 4
    for name, color, lt in layers:
        doc.layers.add(name, color=color, linetype=lt)
    return doc


def write_board_dxf(segs, groove):
    doc = new_dxf([
        ("01_PROFILE_THROUGH_18mm", 1, "Continuous"),
        ("02_POCKET_DEPTH_8mm", 5, "Continuous"),
        ("03_CENTERLINE_REF_NOCUT", 8, "DASHED"),
        ("09_NOTES_NOCUT", 7, "Continuous"),
    ])
    msp = doc.modelspace()
    add_rounded_rect_dxf(msp, 0, 0, W, H, CORNER_R, "01_PROFILE_THROUGH_18mm")
    add_poly_dxf(msp, groove, "02_POCKET_DEPTH_8mm")
    for s in segs:
        (x1, y1), (x2, y2) = s.coords
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": "03_CENTERLINE_REF_NOCUT"})
    notes = [
        "BRIDGE CARE MAZE L2  400x300x18  BIRCH PLY 18T  UNIT: mm  ORIGIN: bottom-left",
        "01_PROFILE: outside cut, through 18mm (use tabs)",
        "02_POCKET: pocket 8.0mm deep, groove width 12.0mm, cut BEFORE profile",
        "03_CENTERLINE: reference only (12mm straight bit single pass is also OK)",
        "Top edge round-over R3 after cutting. Sand groove walls #180.",
    ]
    for i, t in enumerate(notes):
        msp.add_text(t, height=4, dxfattribs={"layer": "09_NOTES_NOCUT"}).set_placement((0, -12 - i * 7))
    doc.saveas(OUT / "maze_L2_board_CNC.dxf")


def coupon_slots(x, y):
    """공차 테스트 조각: 홈 폭 11.5 / 12.0 / 12.5"""
    slots = []
    for i, w in enumerate((11.5, 12.0, 12.5)):
        cx = x + 30 + i * 45
        slots.append((w, LineString([(cx, y + 15), (cx, y + 55)]).buffer(w / 2, quad_segs=16)))
    return slots


def write_blocks_dxf():
    doc = new_dxf([
        ("01_PROFILE_THROUGH_18mm", 1, "Continuous"),
        ("02_POCKET_DEPTH_8mm", 5, "Continuous"),
        ("04_DRILL_D10_DEPTH10", 3, "Continuous"),
        ("09_NOTES_NOCUT", 7, "Continuous"),
    ])
    msp = doc.modelspace()
    for i in range(4):
        x = 10 + i * (BLOCK + 15)
        add_rounded_rect_dxf(msp, x, 10, BLOCK, BLOCK, BLOCK_R, "01_PROFILE_THROUGH_18mm")
        msp.add_circle((x + BLOCK / 2, 10 + BLOCK / 2), PEG_D / 2, dxfattribs={"layer": "04_DRILL_D10_DEPTH10"})
    # 테스트 조각
    add_rounded_rect_dxf(msp, 10, 80, 150, 70, 5, "01_PROFILE_THROUGH_18mm")
    for w, s in coupon_slots(10, 80):
        add_poly_dxf(msp, s, "02_POCKET_DEPTH_8mm")
    notes = [
        "4 BLOCKS 50x50x18 R8 + 1 TEST COUPON 150x70 (grooves 11.5 / 12.0 / 12.5 deep 8)",
        "04_DRILL: D10 hole, 10mm deep, centre of block (this face = BOTTOM, print the other face)",
        "Glue D10 wood dowel, 16mm long -> 6mm sticks out. Chamfer dowel tip 1mm.",
        "Round-over all block edges R3.",
    ]
    for i, t in enumerate(notes):
        msp.add_text(t, height=4, dxfattribs={"layer": "09_NOTES_NOCUT"}).set_placement((0, -12 - i * 7))
    doc.saveas(OUT / "maze_L2_blocks_CNC.dxf")


# ─────────────────────────── 인쇄 그래픽 ───────────────────────────
def print_graphics(groove):
    """판 위 인쇄 요소: [(폴리곤, 색, 이름)]  홈에서 PRINT_CLEAR 만큼 떨어지도록 잘라냄"""
    mask = groove.buffer(PRINT_CLEAR, quad_segs=8)
    items = []
    for c, kind in TARGETS.items():
        cx, cy = node(c, ROWS - 1)
        ring = rounded_rect(cx - FRAME_OUT / 2, cy - FRAME_OUT / 2, FRAME_OUT, FRAME_OUT, 10).difference(
            rounded_rect(cx - FRAME_IN / 2, cy - FRAME_IN / 2, FRAME_IN, FRAME_IN, 8))
        items.append((ring.difference(mask), COLORS[kind], f"target-frame-{kind}"))
        fill, line = shape_parts(kind, cx, cy, 38)
        items.append((fill.difference(mask), COLORS[kind], f"target-shape-{kind}"))
        items.append((line.difference(mask), OUTLINE, f"target-outline-{kind}"))
    for c, kind in STARTS.items():
        cx, cy = node(c, 0)
        ring = rounded_rect(cx - 29, cy - 29, 58, 58, 10).difference(
            rounded_rect(cx - 27, cy - 27, 54, 54, 9))
        items.append((ring.difference(mask), COLORS[kind], f"start-frame-{kind}"))
        # 출발 표시 그림은 홈 끝(R6) 아래쪽 빈 곳에 작게 → 블록을 치우면 '제자리'가 보임
        fill, line = shape_parts(kind, cx, cy - 16, 14, line=1.0)
        items.append((fill.difference(mask), COLORS[kind], f"start-shape-{kind}"))
        items.append((line.difference(mask), OUTLINE, f"start-outline-{kind}"))
    return items


TITLE = "브릿지케어 · 길 찾기 미로 2단계"


def write_print_svgs(groove):
    items = print_graphics(groove)
    title_d = text_outline_path(TITLE, W / 2, H - 4.5, 6.5)
    body = ['<g id="PRINT_CMYK">']
    for geom, color, name in items:
        body.append(f'<path id="{name}" d="{path_d(geom)}" fill="{color}" fill-rule="evenodd"/>')
    body.append(f'<path id="title" d="{title_d}" fill="#5A4632"/>')
    body.append("</g>")
    guide = [f'<g id="GUIDE_DO_NOT_PRINT" fill="none" stroke="#FF00FF" stroke-width="0.3">',
             f'<path d="{path_d(rounded_rect(0, 0, W, H, CORNER_R))}"/>',
             f'<path d="{path_d(groove)}"/>', "</g>"]
    (OUT / "maze_L2_board_PRINT.svg").write_text(svg_doc(W, H, "\n".join(body + guide)), encoding="utf-8")

    white = unary_union([g for g, color, _ in items])
    wbody = (f'<g id="WHITE_UNDERBASE"><path d="{path_d(white)}" fill="#000000" fill-rule="evenodd"/>'
             f'<path d="{title_d}" fill="#000000"/></g>' + "\n".join(guide))
    (OUT / "maze_L2_board_PRINT_white.svg").write_text(svg_doc(W, H, wbody), encoding="utf-8")

    # 블록 윗면 인쇄 (블록 DXF 와 같은 배치)
    bw, bh = 10 + 4 * (BLOCK + 15), 70
    tx = lambda x, y: (x, bh - y)
    b = ['<g id="PRINT_CMYK">']
    g2 = ['<g id="GUIDE_DO_NOT_PRINT" fill="none" stroke="#FF00FF" stroke-width="0.3">']
    for i, kind in enumerate(["circle", "triangle", "square", "star"]):
        x = 10 + i * (BLOCK + 15)
        cx, cy = x + BLOCK / 2, 10 + BLOCK / 2
        fill, line = shape_parts(kind, cx, cy, 38)
        b.append(f'<path id="block-{kind}" d="{path_d(fill, tx)}" fill="{COLORS[kind]}"/>')
        b.append(f'<path d="{path_d(line, tx)}" fill="{OUTLINE}" fill-rule="evenodd"/>')
        g2.append(f'<path d="{path_d(rounded_rect(x, 10, BLOCK, BLOCK, BLOCK_R), tx)}"/>')
    b.append("</g>")
    g2.append("</g>")
    (OUT / "maze_L2_blocks_PRINT.svg").write_text(svg_doc(bw, bh, "\n".join(b + g2)), encoding="utf-8")
    return items, title_d


# ─────────────────────────── 미리보기 / 정답지 ───────────────────────────
def board_art(groove, items, title_d, blocks=True, routes=None, g=None):
    defs = """
<filter id="sh" x="-20%" y="-20%" width="140%" height="140%">
  <feDropShadow dx="1.2" dy="1.8" stdDeviation="1.4" flood-color="#000" flood-opacity="0.35"/></filter>
<filter id="inner" x="-5%" y="-5%" width="110%" height="110%">
  <feOffset dx="0.8" dy="1.2"/><feGaussianBlur stdDeviation="0.8" result="o"/>
  <feComposite in="SourceGraphic" in2="o" operator="arithmetic" k2="-1" k3="1" result="s"/>
  <feFlood flood-color="#5a3c1c" flood-opacity="0.55"/><feComposite in2="s" operator="in"/>
  <feComposite in2="SourceGraphic" operator="over"/></filter>
<linearGradient id="wood" x1="0" y1="0" x2="1" y2="0.15">
  <stop offset="0" stop-color="#EFD9B4"/><stop offset="0.5" stop-color="#F3E0BF"/><stop offset="1" stop-color="#E8CFA6"/></linearGradient>
"""
    out = [f'<g filter="url(#sh)"><path d="{path_d(rounded_rect(0, 0, W, H, CORNER_R))}" fill="url(#wood)"/></g>']
    for i in range(0, int(H), 9):
        out.append(f'<path d="M6,{i + 3} C120,{i + 5} 260,{i + 1} 394,{i + 4}" stroke="#D9BE93" '
                   f'stroke-width="0.35" fill="none" opacity="0.5"/>')
    out.append(f'<path d="{path_d(groove)}" fill="#B88A55" fill-rule="evenodd" filter="url(#inner)"/>')
    for geom, color, _ in items:
        out.append(f'<path d="{path_d(geom)}" fill="{color}" fill-rule="evenodd"/>')
    out.append(f'<path d="{title_d}" fill="#5A4632"/>')
    if routes:
        offs = {"circle": -3.6, "triangle": -1.2, "square": 1.2, "star": 3.6}
        for kind, p in routes.items():
            ls = LineString([node(*n) for n in p]).offset_curve(offs[kind], join_style=2)
            pts = " ".join(f"{x:.2f},{fy(y):.2f}" for x, y in ls.coords)
            out.append(f'<polyline points="{pts}" fill="none" stroke="{COLORS[kind]}" stroke-width="2.2" '
                       f'stroke-linejoin="round" stroke-linecap="round" marker-end="url(#arr-{kind})"/>')
        for kind, col in COLORS.items():
            defs += (f'<marker id="arr-{kind}" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" '
                     f'markerHeight="4" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
        for n, nb in g.items():
            if len(nb) == 1 and 0 < n[1] < ROWS - 1:
                x, y = node(*n)
                out.append(f'<g stroke="#444" stroke-width="1.4"><line x1="{x - 3.5}" y1="{fy(y) - 3.5}" '
                           f'x2="{x + 3.5}" y2="{fy(y) + 3.5}"/><line x1="{x + 3.5}" y1="{fy(y) - 3.5}" '
                           f'x2="{x - 3.5}" y2="{fy(y) + 3.5}"/></g>')
    if blocks:
        for c, kind in STARTS.items():
            cx, cy = node(c, 0)
            bx, by = cx - BLOCK / 2, cy - BLOCK / 2
            out.append(f'<g filter="url(#sh)"><path d="{path_d(rounded_rect(bx, by, BLOCK, BLOCK, BLOCK_R))}" '
                       f'fill="#F6E4C4" stroke="#C9A877" stroke-width="0.6"/></g>')
            fill, line = shape_parts(kind, cx, cy, 38)
            out.append(f'<path d="{path_d(fill)}" fill="{COLORS[kind]}"/>')
            out.append(f'<path d="{path_d(line)}" fill="{OUTLINE}" fill-rule="evenodd"/>')
    return defs, "\n".join(out)


def write_previews(groove, items, title_d, routes, g):
    pad = 12
    vb = f"{-pad} {-pad} {W + 2 * pad} {H + 2 * pad}"
    defs, art = board_art(groove, items, title_d, blocks=True)
    (OUT / "preview.svg").write_text(svg_doc(W + 2 * pad, H + 2 * pad, art, defs, vb, None)
                                     .replace(f'<svg ', '<svg style="background:#F7F4EE" ', 1), encoding="utf-8")
    defs, art = board_art(groove, items, title_d, blocks=False, routes=routes, g=g)
    (OUT / "answer_key.svg").write_text(svg_doc(W + 2 * pad, H + 2 * pad, art, defs, vb, None)
                                        .replace(f'<svg ', '<svg style="background:#FFFFFF" ', 1), encoding="utf-8")


# ─────────────────────────── 제작 도면 (A3) ───────────────────────────
def drawing_svg(groove, segs, routes, dead_ends, branches):
    SW, SH = 420, 297
    s = 0.5                     # 평면도 1:2
    ox, oy = 32, 48
    P = lambda x, y: (ox + x * s, oy + (H - y) * s)
    o = []
    font = 'font-family="WenQuanYi Zen Hei, sans-serif"'

    def text(x, y, t, size=3.2, anchor="start", weight="normal", fill="#111"):
        o.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" {font} text-anchor="{anchor}" '
                 f'font-weight="{weight}" fill="{fill}" stroke="#fff" stroke-width="0.6" paint-order="stroke">{t}</text>')

    def line(x1, y1, x2, y2, w=0.25, col="#111", dash=None, markers=""):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{col}" '
                 f'stroke-width="{w}"{d} {markers}/>')

    ARR = 'marker-start="url(#a)" marker-end="url(#a)"'

    def dim_h(xa, xb, y, ext_from, label, size=2.8):
        line(xa, ext_from, xa, y + 1.5, 0.18)
        line(xb, ext_from, xb, y + 1.5, 0.18)
        line(xa, y, xb, y, 0.2, markers=ARR)
        text((xa + xb) / 2, y - 1.2, label, size, "middle")

    def dim_v(ya, yb, x, ext_from, label, size=2.8, side=-1):
        line(ext_from, ya, x - 1.5 * side, ya, 0.18)
        line(ext_from, yb, x - 1.5 * side, yb, 0.18)
        line(x, ya, x, yb, 0.2, markers=ARR)
        tx, ty = x + side * 1.4, (ya + yb) / 2
        o.append(f'<text x="{tx:.2f}" y="{ty:.2f}" font-size="{size}" {font} text-anchor="middle" '
                 f'transform="rotate(-90 {tx:.2f} {ty:.2f})">{label}</text>')

    # 테두리 + 제목
    o.append(f'<rect x="8" y="8" width="{SW - 16}" height="{SH - 16}" fill="none" stroke="#111" stroke-width="0.5"/>')
    text(16, 20, "브릿지케어 인지교구 · 길 찾기 미로판 2단계(경증) — 제작 도면", 6, weight="bold")
    text(16, 27, "400 × 300 × 18 mm 자작나무 합판 · CNC 홈 가공 + UV 인쇄 · 블록 4개", 3.4, fill="#444")

    # ── 평면도
    tr = lambda x, y: P(x, y)
    o.append(f'<path d="{path_d(rounded_rect(0, 0, W, H, CORNER_R), tr)}" fill="#FBF6EC" stroke="#111" stroke-width="0.45"/>')
    o.append(f'<path d="{path_d(groove, tr)}" fill="#D8C3A0" stroke="#111" stroke-width="0.3" fill-rule="evenodd"/>')
    for sgm in segs:
        (x1, y1), (x2, y2) = sgm.coords
        a, b = P(x1, y1), P(x2, y2)
        line(*a, *b, 0.15, "#7A6A55", "2,1")
    for c, kind in TARGETS.items():
        x, y = P(*node(c, ROWS - 1))
        fill, ln = shape_parts(kind, *node(c, ROWS - 1), 38)
        o.append(f'<path d="{path_d(fill, tr)}" fill="{COLORS[kind]}" opacity="0.85"/>')
        o.append(f'<rect x="{x - 15}" y="{y - 15}" width="30" height="30" rx="5" fill="none" '
                 f'stroke="{COLORS[kind]}" stroke-width="1.6" opacity="0.85"/>')
    for c, kind in STARTS.items():
        x, y = P(*node(c, 0))
        o.append(f'<rect x="{x - 12.5}" y="{y - 12.5}" width="25" height="25" rx="4" fill="#fff" '
                 f'fill-opacity="0.6" stroke="#555" stroke-width="0.3" stroke-dasharray="1.2,0.8"/>')
        fill, ln = shape_parts(kind, *node(c, 0), 30)
        o.append(f'<path d="{path_d(fill, tr)}" fill="{COLORS[kind]}"/>')
    for n in dead_ends:
        x, y = P(*node(*n))
        o.append(f'<circle cx="{x}" cy="{y}" r="2.2" fill="none" stroke="#C00" stroke-width="0.35"/>')
    # 단면 표시선 A-A (도착 '별' 칸 아래 세로 홈을 가로로 자름)
    ax = node(4, 3)[0]
    ay = (node(4, 3)[1] + node(4, 4)[1]) / 2 - 8
    a1, a2 = P(ax - 32, ay), P(ax + 32, ay)
    line(*a1, *a2, 0.3, "#C00", "3,1,0.6,1")
    text(a1[0] - 2.5, a1[1] + 1, "A", 3, "middle", "bold", "#C00")
    text(a2[0] + 2.5, a2[1] + 1, "A", 3, "middle", "bold", "#C00")

    bx0, by0 = P(0, H)
    bx1, by1 = P(W, 0)
    dim_h(bx0, bx1, by0 - 8, by0 - 1, "400")
    dim_v(by0, by1, bx0 - 9, bx0 - 1, "300", side=-1)
    nx0, ny0 = P(*node(0, 0))
    nx1, _ = P(*node(1, 0))
    dim_h(bx0, nx0, by1 + 7, by1 + 1, "45", 2.4)
    dim_h(nx0, nx1, by1 + 7, ny0 + 13, f"{PITCH_X:.2f}", 2.4)
    _, ry1 = P(*node(6, 1))
    nx6, ny6 = P(*node(6, 0))
    dim_v(ny6, ry1, bx1 + 8, nx6 + 13, f"{PITCH_Y:.1f}", 2.4, side=1)
    dim_v(by1, ny6, bx1 + 8, bx1 + 1, "45", 2.4, side=1)
    # 홈 폭 콜아웃
    gx, gy = P(node(4, 0)[0], (node(4, 0)[1] + node(4, 1)[1]) / 2 + 4)
    line(gx - 3, gy, gx + 3, gy, 0.2, markers=ARR)
    line(gx + 3, gy, gx + 40, by1 + 7, 0.18)
    text(gx + 41, by1 + 8, "홈 폭 12 / 깊이 8 / 끝 R6", 2.6)
    cx_, cy_ = P(W, H)
    line(cx_ - 2.2, cy_ + 2.2, cx_ + 6, cy_ - 4, 0.18)
    text(cx_ + 6.5, cy_ - 4.5, "R15", 2.6)
    text(ox + W * s / 2, by1 + 18, "평면도 (위에서 본 모습)  척도 1:2", 3.4, "middle", "bold")
    lg = "".join(f'<tspan fill="{COLORS[k]}">●</tspan>{NAMES[k]}  ' for k in ("circle", "triangle", "square", "star"))
    o.append(f'<text x="{ox}" y="{by1 + 24}" font-size="2.5" {font} fill="#444">{lg}/  아래 줄 = 출발(어르신 쪽), '
             f'위 줄 = 도착  /  <tspan fill="#C00">○</tspan> = 막다른 길</text>')

    # ── 단면 A-A  (척도 2:1)
    k = 2.0
    sx, sy = 322, 92           # 판 윗면 중앙 기준점
    half = 24                  # 판 보이는 폭 (좌우 실제 24mm 씩)
    o.append(f'<defs><pattern id="hatch" width="2.2" height="2.2" patternUnits="userSpaceOnUse" '
             f'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="2.2" stroke="#8B6B43" '
             f'stroke-width="0.35"/></pattern></defs>')
    gw, gd = GROOVE_W * k, GROOVE_D * k
    tk = T * k
    board = (f"M{sx - half * k},{sy} L{sx - gw / 2},{sy} L{sx - gw / 2},{sy + gd} L{sx + gw / 2},{sy + gd} "
             f"L{sx + gw / 2},{sy} L{sx + half * k},{sy} L{sx + half * k},{sy + tk} L{sx - half * k},{sy + tk} Z")
    o.append(f'<path d="{board}" fill="url(#hatch)" stroke="#111" stroke-width="0.4"/>')
    # 끊김선
    for xx in (sx - half * k, sx + half * k):
        o.append(f'<path d="M{xx},{sy - 3} l-2,6 l4,4 l-2,{tk - 4}" fill="none" stroke="#111" stroke-width="0.2"/>')
    bwk, btk = BLOCK * k, T * k
    o.append(f'<rect x="{sx - bwk / 2}" y="{sy - btk - 0.6}" width="{bwk}" height="{btk}" rx="{3 * k}" '
             f'fill="#F3E3C6" stroke="#111" stroke-width="0.4"/>')
    pk = PEG_D * k
    hole_top = sy - 0.6 - PEG_HOLE * k
    peg_bot = sy - 0.6 + PEG_OUT * k
    o.append(f'<rect x="{sx - pk / 2}" y="{hole_top}" width="{pk}" height="{peg_bot - hole_top}" '
             f'fill="#E2C38F" stroke="#111" stroke-width="0.35" rx="1"/>')
    text(sx, sy - btk / 2 - 6, "블록 50×50×18", 2.6, "middle")
    # 치수
    dim_v(sy, sy + tk, sx - half * k - 9, sx - half * k, "18 (판)", 2.4)
    dim_v(sy, sy + gd, sx + half * k + 8, sx + gw / 2, "8 (홈 깊이)", 2.3, side=1)
    dim_h(sx - gw / 2, sx + gw / 2, sy + tk + 7, sy + gd, "12 (홈 폭)", 2.4)
    dim_h(sx - bwk / 2, sx + bwk / 2, sy - btk - 8, sy - btk, "50", 2.4)
    dim_v(sy - btk - 0.6, sy - 0.6, sx + bwk / 2 + 8, sx + bwk / 2, "18", 2.4, side=1)
    line(sx + pk / 2, peg_bot - 2, sx + 30, peg_bot + 42, 0.18)
    text(sx + 30, peg_bot + 45, "목심 Ø10 × 16 (블록에 10 박고 6 돌출)", 2.4, "middle")
    line(sx - pk / 2, peg_bot + 1.5, sx - 34, peg_bot + 42, 0.18)
    text(sx - 34, peg_bot + 45, "목심 끝 ~ 홈 바닥 여유 2", 2.4, "middle")
    text(sx, 157, "단면 A-A  척도 2:1", 3.4, "middle", "bold")

    # ── 블록 윗면 (1:1)
    bx, byy = 262, 168
    o.append(f'<rect x="{bx}" y="{byy}" width="50" height="50" rx="8" fill="#F3E3C6" stroke="#111" stroke-width="0.4"/>')
    o.append(f'<circle cx="{bx + 25}" cy="{byy + 25}" r="5" fill="none" stroke="#111" stroke-width="0.3" stroke-dasharray="1,0.6"/>')
    line(bx + 25, byy + 18, bx + 25, byy + 32, 0.15, dash="3,1,0.6,1")
    line(bx + 18, byy + 25, bx + 32, byy + 25, 0.15, dash="3,1,0.6,1")
    dim_h(bx, bx + 50, byy - 5, byy, "50", 2.4)
    text(bx + 56, byy + 8, "블록 (밑면)  척도 1:1", 3, weight="bold")
    text(bx + 56, byy + 15, "· 4개: 빨강●  파랑▲  노랑■  초록★", 2.5)
    text(bx + 56, byy + 21, "· 밑면 가운데 Ø10 구멍, 깊이 10", 2.5)
    text(bx + 56, byy + 27, "· 모든 모서리 R3 라운딩", 2.5)
    text(bx + 56, byy + 33, "· 윗면에 모양 UV 인쇄 (38mm)", 2.5)
    text(bx + 56, byy + 39, "· 어르신이 잡기 쉬운 크기", 2.5)
    text(bx + 56, byy + 45, "  (삼킴 위험 없음)", 2.5)

    # ── 메모
    notes = [
        ("CNC 가공 (파일: maze_L2_board_CNC.dxf)", True),
        ("① 02_POCKET 레이어: 깊이 8.0 포켓 가공 (Ø6 엔드밀 권장) → ② 01_PROFILE: 외곽 관통 컷(탭 남김)", False),
        ("③ 03_CENTERLINE 은 참고선(가공 안 함). Ø12 일자 비트 1회 통과로 가공해도 됨", False),
        ("④ 판 윗면 외곽 R3 트리머 라운딩, 홈 안쪽 #180 샌딩 — 블록이 걸림 없이 미끄러져야 함", False),
        ("UV 인쇄 (파일: maze_L2_board_PRINT.svg + _white.svg)", True),
        ("판 원점(왼쪽 아래)을 지그에 맞춰 인쇄. 화이트 깔고 컬러. 홈 가장자리 1.5mm 안쪽엔 인쇄 없음", False),
        ("마감: 무광 수성 UV 코팅 또는 수성 바니시 2회 (알코올 소독 견딤)", False),
        ("시제품 먼저: 테스트 조각(홈 11.5/12/12.5)으로 목심이 가장 부드럽게 움직이는 폭 확인 후 본가공", True),
    ]
    yy = 232
    for t, bold in notes:
        text(16, yy, t, 2.7 if not bold else 2.9, weight="bold" if bold else "normal",
             fill="#111" if bold else "#333")
        yy += 6.2 if bold else 5.6

    # ── 표제란
    tx0, ty0 = 262, 236
    o.append(f'<rect x="{tx0}" y="{ty0}" width="150" height="53" fill="none" stroke="#111" stroke-width="0.4"/>')
    rows = [("품명", "길 찾기 미로판 2단계(경증)"), ("규격", "400 × 300 × 18 mm"),
            ("재질", "자작나무 합판 18T (원판 1220×2440)"), ("단위 / 척도", "mm / 평면 1:2, 단면 2:1"),
            ("도면번호", "BC-MZ-L2-01   작성 2026-11-23"),
            ("미로", f"출발 4 · 도착 4 · 갈래점 {len(branches)} · 막다른 길 {len(dead_ends)}")]
    for i, (a, b) in enumerate(rows):
        y = ty0 + 8.6 * i
        if i:
            line(tx0, y, tx0 + 150, y, 0.2)
        text(tx0 + 3, y + 6, a, 2.7, weight="bold")
        text(tx0 + 32, y + 6, b, 2.8)
    line(tx0 + 29, ty0, tx0 + 29, ty0 + 53, 0.2)

    defs = ('<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="3.2" markerHeight="3.2" '
            'orient="auto-start-reverse"><path d="M0,1 L10,5 L0,9 z" fill="#111"/></marker>')
    (OUT / "drawing_A3.svg").write_text(svg_doc(SW, SH, "\n".join(o), defs, bg="#FFFFFF"), encoding="utf-8")


def main():
    g, routes, dead_ends, branches = check_maze()
    segs, groove = groove_geometry()
    # 안전 확인: 홈이 판 가장자리에서 충분히 떨어져 있는가
    minx, miny, maxx, maxy = groove.bounds
    assert min(minx, miny, W - maxx, H - maxy) >= 25, "홈이 가장자리에 너무 가까움"
    write_board_dxf(segs, groove)
    write_blocks_dxf()
    items, title_d = write_print_svgs(groove)
    write_previews(groove, items, title_d, routes, g)
    drawing_svg(groove, segs, routes, dead_ends, branches)
    print("미로 확인 OK")
    for k, p in routes.items():
        print(f"  {NAMES[k]:4s}: {' → '.join(f'({c},{r})' for c, r in p)}")
    print(f"  갈림길 {len(branches)}개, 막다른 길 {len(dead_ends)}개: {dead_ends}")
    print(f"  홈 면적 {groove.area:.0f} mm², 가장자리 여유 {min(minx, miny, W - maxx, H - maxy):.1f} mm")
    print("생성:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
