# -*- coding: utf-8 -*-
"""把 Wind MCP 的原始返回拼成 draw_rank.py 需要的 raw.json

份额变化来自两次 search_funds（增加侧/减少侧），均价与涨跌幅来自行情接口或本地缓存。
本脚本按 Wind 代码自动对齐，不手工拼数据。

用法（价格走缓存，推荐）：
    python build_raw.py --inflow inflow.json --outflow outflow.json \
        --price-cache cache --pct-field 5日涨跌幅 --out raw.json \
        --period-label "周度资金流 · 2026/10/19-10/23"

用法（价格直接传返回文件）：
    python build_raw.py --inflow a.json --outflow b.json \
        --price price1.json price2.json --pct-field 5日涨跌幅 --out raw.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wind_io import PCT_FIELDS, codes_of, num, pick_change_col, to_records  # noqa: E402


def load_from_files(paths):
    """从行情返回文件读 {code: {name, avg, pct{...}}}"""
    out = {}
    for path in paths:
        for rec in to_records(path):
            code = rec.get("Wind代码") or rec.get("代码")
            if not code:
                continue
            out[str(code)] = {
                "name": rec.get("中文简称") or rec.get("证券简称") or str(code),
                "avg": num(rec.get("最新均价")),
                "pct": {f: num(rec.get(f)) for f in PCT_FIELDS},
            }
    return out


def load_from_cache(cache_dir):
    """从缓存目录读所有 price_*.json，后写的覆盖先写的"""
    out = {}
    if not os.path.isdir(cache_dir):
        return out
    for name in sorted(os.listdir(cache_dir)):
        if not (name.startswith("price_") and name.endswith(".json")):
            continue
        with open(os.path.join(cache_dir, name), encoding="utf-8") as fh:
            for code, v in json.load(fh).items():
                if v.get("avg"):
                    out[str(code)] = {"name": v.get("name", code), "avg": v["avg"],
                                      "pct": v.get("pct") or {}}
    return out


def main():
    ap = argparse.ArgumentParser(description="Wind 原始返回 -> raw.json")
    ap.add_argument("--inflow", required=True, help="份额增加侧 search_funds 返回的 json")
    ap.add_argument("--outflow", required=True, help="份额减少侧 search_funds 返回的 json")
    ap.add_argument("--price", nargs="*", default=None, help="行情返回 json（不走缓存时用）")
    ap.add_argument("--price-cache", default=None, help="行情缓存目录，与 --price 二选一即可")
    ap.add_argument("--pct-field", default="5日涨跌幅", choices=PCT_FIELDS,
                    help="图上展示哪个涨跌幅列，默认 5日涨跌幅")
    ap.add_argument("--pct-label", default=None, help="图上列名，默认沿用 --pct-field")
    ap.add_argument("--hide-pct", action="store_true", help="不显示涨跌幅列（自定义区间时用）")
    ap.add_argument("--out", required=True, help="输出 raw.json 路径")
    ap.add_argument("--period-label", default="")
    ap.add_argument("--title", default="ETF资金流向")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--insight", nargs="*", default=[])
    ap.add_argument("--footer", nargs="*", default=None, help="脚注行，默认用标准免责声明")
    ap.add_argument("--brand", default="@望京博格")
    ap.add_argument("--keep-zero", action="store_true", help="保留份额变化为 0 的行")
    args = ap.parse_args()

    if not args.price and not args.price_cache:
        sys.exit("需要 --price-cache 或 --price 之一")

    # 1. 份额变化（两侧合并去重，同号取后出现的）
    dshare = {}
    for path in (args.inflow, args.outflow):
        for rec in to_records(path):
            code = rec.get("Wind代码") or rec.get("代码")
            if not code:
                continue
            col = pick_change_col(rec)
            if not col:
                sys.exit("%s 里找不到「份额变化」列，实际列名：%s" % (path, list(rec)))
            val = num(rec[col])
            if val is None or (val == 0 and not args.keep_zero):
                continue
            dshare[str(code)] = val
    if not dshare:
        sys.exit("没有解析到任何份额变化数据")

    # 2. 行情
    quotes = {}
    if args.price_cache:
        quotes.update(load_from_cache(args.price_cache))
    if args.price:
        quotes.update(load_from_files(args.price))

    # 3. 合并
    rows, skipped = [], []
    for code, ds in dshare.items():
        q = quotes.get(code)
        if not q or not q["avg"]:
            skipped.append(code)
            continue
        pct = None if args.hide_pct else q["pct"].get(args.pct_field)
        # 注意：这里不做跨字段兜底。字段缺失就让它是 None（图上显示 "-"），
        # 否则会把 5日涨跌幅 当成 年初至今涨跌幅 显示，属于造假。
        rows.append({"code": code, "name": q["name"], "dshare": ds, "avg": q["avg"], "pct": pct})

    if not rows:
        sys.exit("份额与行情没有交集：检查份额返回与行情是否同一批代码、缓存是否属同一交易日")

    footer = args.footer or [
        "口径：净流入 = 区间内场内流通份额变化 × 区间成交均价；仅统计股票型ETF，不含跨境/商品/债券。",
        "数据来源：Wind。本图仅供信息参考，不构成投资建议。",
    ]
    meta = {
        "period_label": args.period_label,
        "title": args.title,
        "subtitle": args.subtitle,
        "pct_label": "" if args.hide_pct else (args.pct_label or args.pct_field),
        "insight": args.insight,
        "footnote": footer,
        "brand": args.brand,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "rows": rows}, fh, ensure_ascii=False, indent=1)

    n_in = sum(1 for r in rows if r["dshare"] > 0)
    print("saved: %s  行数 %d（申购 %d / 赎回 %d）" % (args.out, len(rows), n_in, len(rows) - n_in))
    if skipped:
        print("注意：%d 只没取到均价已剔除（多半是缓存里没有该代码）：%s"
              % (len(skipped), ",".join(sorted(skipped)[:12])))
    if not args.hide_pct:
        missing = [r["code"] for r in rows if r["pct"] is None]
        if missing:
            print("警告：%d 只缺「%s」字段，图上会显示 '-'（不会用其他周期顶替）。"
                  "要补全请对以下代码重取行情：%s"
                  % (len(missing), args.pct_field, ",".join(missing[:15])))


if __name__ == "__main__":
    main()
