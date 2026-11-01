# -*- coding: utf-8 -*-
"""ETF资金流向榜单一图生成器

读取 raw.json（份额变化 + 均价 + 涨跌幅），自动计算净流入金额、排序、取前 N，
输出一张 1080px 宽的小红书/公众号榜单图。

用法：
    python draw_rank.py --input raw.json --out out.png
    python draw_rank.py --input raw.json --out out.png --top 20 --only inflow

raw.json 结构：
{
  "meta": {
    "period_label": "周度资金流 · 2026/10/19-10/23",
    "title": "本周ETF：钱去哪了",
    "subtitle": "指数还在跌，宽基却被买爆了",
    "pct_label": "周涨跌幅",
    "insight": ["净流入前9名清一色宽基；", "半导体设备被赎回近35亿份。"],
    "footnote": ["口径：...", "数据来源：Wind。"],
    "brand": "@望京博格"
  },
  "rows": [
    {"code": "510300.SH", "name": "沪深300ETF华泰柏瑞", "dshare": 6689700000, "avg": 4.10672, "pct": -1.37}
  ]
}

字段说明：
  dshare  份额变化，正=净申购 负=净赎回。单位写"份"或"亿份"都行（绝对值>1e5 视为"份"自动换算）
  avg     区间内成交均价（元），用于把份额变化折成金额
  pct     区间涨跌幅（%），没有就填 null 或删掉该字段，图上自动隐藏该列
"""

import argparse
import json
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("缺少 Pillow，请先安装：pip install pillow")

# ---------------- 主题 ----------------
BG = (251, 250, 247)
INK = (26, 26, 26)
GRAY = (138, 138, 138)
LGRAY = (196, 196, 196)
RED = (211, 47, 47)          # 净流入 / 上涨（A股习惯：红涨）
RED_BG = (252, 235, 235)
GREEN = (26, 138, 88)        # 净流出 / 下跌
GREEN_BG = (231, 244, 236)
LINE = (232, 228, 220)
ZEBRA = (246, 243, 237)
NOTE_BG = (243, 239, 231)
W = 1080
M = 55

FONT_CANDIDATES = [
    ("C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc"),
    ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/PingFang.ttc"),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
     "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ("C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simhei.ttf"),
]


def pick_fonts():
    for bold, regular in FONT_CANDIDATES:
        if os.path.exists(bold) and os.path.exists(regular):
            return bold, regular
    sys.exit("未找到可用中文字体，请在 FONT_CANDIDATES 中补充本机字体路径")


BOLD_PATH, REG_PATH = pick_fonts()
_cache = {}


def f(size, bold=False):
    key = (size, bold)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(BOLD_PATH if bold else REG_PATH, size)
    return _cache[key]


def to_yi(v):
    """份额统一换算成「亿份」：绝对值大于 1e5 视为原始「份」"""
    return v / 1e8 if abs(v) > 1e5 else float(v)


def fmt_amt(v, signed=True):
    """金额统一两位小数，不按量级取整（否则千亿级榜单里精度会不一致）"""
    s = "%+.2f" % v
    return s if signed else s.lstrip("+")


def load_data(path):
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    meta = raw.get("meta", {}) or {}
    rows = []
    for r in raw.get("rows", []):
        ds = to_yi(float(r["dshare"]))
        avg = float(r["avg"])
        pct = r.get("pct", None)
        rows.append({
            "code": str(r["code"]),
            "name": str(r["name"]),
            "dshare": ds,
            "avg": avg,
            "pct": None if pct is None else float(pct),
            "amt": round(ds * avg, 2),
        })
    if not rows:
        sys.exit("raw.json 里没有 rows 数据")
    return meta, rows


def draw_block(d, y, title, tcolor, tbg, rows, amt_head, pct_label, cols, abs_amt=False):
    d.rounded_rectangle([M, y, M + 248, y + 36], radius=8, fill=tbg)
    d.text((M + 14, y + 6), title, font=f(22, True), fill=tcolor)
    y += 50

    d.text((cols["rank"], y), "#", font=f(15), fill=LGRAY)
    d.text((cols["name"], y), "基金名称 / 代码", font=f(15), fill=LGRAY)
    heads = [("share", "份额变化(亿份)")]
    if pct_label:
        heads.append(("pct", pct_label))
    heads.append(("amt", amt_head))
    for key, txt in heads:
        d.text((cols[key] - d.textlength(txt, font=f(15)), y), txt, font=f(15), fill=LGRAY)
    y += 24
    d.line([M, y, W - M, y], fill=LINE, width=2)
    y += 7

    for i, r in enumerate(rows):
        ry = y + i * 41
        if i % 2 == 1:
            d.rectangle([M - 10, ry, W - M + 10, ry + 41], fill=ZEBRA)

        d.text((cols["rank"], ry + 9), "%02d" % (i + 1), font=f(19, True),
               fill=(180, 180, 180) if i > 2 else tcolor)

        nm = r["name"]
        d.text((cols["name"], ry + 5), nm, font=f(21, True), fill=INK)
        nx = cols["name"] + d.textlength(nm, font=f(21, True)) + 16
        d.text((nx, ry + 16), r["code"], font=f(13), fill=(178, 178, 178))

        s = "%+.2f" % r["dshare"]
        d.text((cols["share"] - d.textlength(s, font=f(17)), ry + 10), s, font=f(17), fill=(90, 90, 90))

        if pct_label:
            if r["pct"] is None:
                d.text((cols["pct"] - d.textlength("-", font=f(17)), ry + 10), "-",
                       font=f(17), fill=LGRAY)
            else:
                p = "%+.2f%%" % r["pct"]
                d.text((cols["pct"] - d.textlength(p, font=f(17)), ry + 10), p, font=f(17),
                       fill=RED if r["pct"] > 0 else GREEN)

        a = fmt_amt(abs(r["amt"]) if abs_amt else r["amt"], signed=not abs_amt)
        aw = d.textlength(a, font=f(26, True))
        d.text((cols["amt"] - aw - 26, ry + 5), a, font=f(26, True), fill=tcolor)
        d.text((cols["amt"] - 22, ry + 13), "亿", font=f(15), fill=tcolor)

    return y + len(rows) * 41


def main():
    ap = argparse.ArgumentParser(description="ETF资金流向榜单一图生成")
    ap.add_argument("--input", required=True, help="raw.json 路径")
    ap.add_argument("--out", required=True, help="输出 png 路径")
    ap.add_argument("--top", type=int, default=None, help="两侧统一取前 N 名（简写）")
    ap.add_argument("--top-in", type=int, default=None, help="净流入取前 N 名，默认 15")
    ap.add_argument("--top-out", type=int, default=None, help="净流出取前 N 名，默认 15")
    ap.add_argument("--only", choices=["both", "inflow", "outflow"], default="both")
    ap.add_argument("--title", default=None)
    ap.add_argument("--subtitle", default=None)
    ap.add_argument("--period-label", default=None)
    ap.add_argument("--pct-label", default=None, help="涨跌幅列名，传空字符串则不显示该列")
    ap.add_argument("--brand", default=None)
    ap.add_argument("--min-height", type=int, default=0, help="画布最小高度，默认按内容自适应")
    args = ap.parse_args()

    meta, rows = load_data(args.input)
    top_in = args.top_in if args.top_in is not None else (args.top if args.top is not None else 15)
    top_out = args.top_out if args.top_out is not None else (args.top if args.top is not None else 15)
    top_in = max(1, top_in)
    top_out = max(1, top_out)

    inflow = sorted([r for r in rows if r["amt"] > 0], key=lambda x: -x["amt"])
    outflow = sorted([r for r in rows if r["amt"] < 0], key=lambda x: x["amt"])

    inflow_top = inflow[:top_in] if args.only in ("both", "inflow") else []
    outflow_top = inflow[:0] if args.only == "inflow" else outflow[:top_out]
    blocks = []
    if inflow_top:
        blocks.append(("inflow", inflow_top))
    if outflow_top:
        blocks.append(("outflow", outflow_top))
    if not blocks:
        sys.exit("没有可绘制的数据（全部为 0 或方向不符）")

    n_in = len(inflow_top)
    n_out = len(outflow_top)
    insight = meta.get("insight") or []
    footnote = meta.get("footnote") or ["数据来源：Wind。本图仅供信息参考，不构成投资建议。"]
    pct_label = args.pct_label if args.pct_label is not None else meta.get("pct_label", "")
    has_pct = bool(pct_label) and any(b[1] and b[1][0]["pct"] is not None for b in blocks)

    block_h = 81 + 41 * n_in if n_in else 0
    block_h2 = (16 + 81 + 41 * n_out) if n_out else 0
    insight_h = (24 + 25 * len(insight)) if insight else 0
    sub = args.subtitle if args.subtitle is not None else meta.get("subtitle", "")
    head_h = 322 if sub else 288          # 无副标题时上移，避免顶部留白
    H = head_h + block_h + block_h2 + \
        (14 + insight_h + 18 if insight else 22) + 14 + 22 * len(footnote) + 40
    H = max(H, args.min_height)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    cols = {"rank": M, "name": M + 52, "share": 505, "pct": 640, "amt": 1025}

    # 顶部
    d.rectangle([0, 0, W, 8], fill=INK)
    d.text((M, 44), meta.get("period_label", ""), font=f(20, True), fill=GRAY)
    d.text((M, 78), args.title or meta.get("title", "ETF资金流向"), font=f(57, True), fill=INK)
    if sub:
        d.text((M, 158), sub, font=f(24), fill=(80, 80, 80))

    # 摘要卡
    s_in = sum(r["amt"] for r in inflow_top)
    s_out = abs(sum(r["amt"] for r in outflow_top))
    cards = []
    if n_in and s_in:
        cards.append(("TOP%d 合计净流入" % n_in, "%.0f" % s_in, "亿元", RED, RED_BG))
    if n_out and s_out:
        cards.append(("TOP%d 合计净流出" % n_out, "%.0f" % s_out, "亿元", GREEN, GREEN_BG))
    card_y = 212 if sub else 178
    cw = (W - 2 * M - 20 * (len(cards) - 1)) // len(cards)
    for i, (label, val, unit, c, cb) in enumerate(cards):
        x0 = M + i * (cw + 20)
        d.rounded_rectangle([x0, card_y, x0 + cw, card_y + 92], radius=14, fill=cb)
        d.text((x0 + 22, card_y + 14), label, font=f(19), fill=GRAY)
        tw = d.textlength(val, font=f(44, True))
        d.text((x0 + 22, card_y + 36), val, font=f(44, True), fill=c)
        d.text((x0 + 26 + tw, card_y + 60), unit, font=f(18), fill=c)

    # 榜单
    y = head_h
    labels = {"inflow": ("净流入 TOP%d" % n_in, "净流入额"),
              "outflow": ("净流出 TOP%d" % n_out, "净流出额")}
    for idx, (kind, g) in enumerate(blocks):
        t, head = labels[kind]
        color, bg = (RED, RED_BG) if kind == "inflow" else (GREEN, GREEN_BG)
        y = draw_block(d, y, t, color, bg, g, head, pct_label if has_pct else None, cols,
                       abs_amt=(kind == "outflow"))
        if idx == 0 and len(blocks) > 1:
            y += 16

    # 看点
    if insight:
        ky = y + 14
        d.rounded_rectangle([M, ky, W - M, ky + 24 + 25 * len(insight)], radius=10, fill=NOTE_BG)
        d.text((M + 18, ky + 10), "看点", font=f(17, True), fill=(120, 108, 84))
        for i, line in enumerate(insight):
            d.text((M + 18, ky + 34 + i * 25), line, font=f(18), fill=(60, 60, 60))
        y = ky + 24 + 25 * len(insight) + 18

    # 底部
    y += 2
    d.line([M, y, W - M, y], fill=LINE, width=2)
    y += 14
    for i, line in enumerate(footnote):
        d.text((M, y + i * 22), line, font=f(16), fill=(122, 122, 122))
    brand = args.brand if args.brand is not None else meta.get("brand", "")
    if brand:
        bw = d.textlength(brand, font=f(18, True))
        d.text((W - M - bw, y + 22 * (len(footnote) - 1) - 2), brand,
               font=f(18, True), fill=(165, 165, 165))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    img.save(args.out, quality=95)
    print("saved:", args.out, "size:", img.size)
    print("净流入合计 %.2f 亿 / 净流出合计 %.2f 亿" % (s_in, s_out))


if __name__ == "__main__":
    main()
