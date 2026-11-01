# -*- coding: utf-8 -*-
"""行情数据本地缓存：同一交易日只取一次价

为什么需要：份额变化每换一个区间都要重取，但**均价和涨跌幅只跟交易日有关**。
今天先看近一周、再看近一个月、今年以来，价格完全一样。没有缓存时每次都重取
100 只 = 2 次调用；有缓存时第二次起是 0 次。

三个子命令：
    plan    给出要用的代码，告诉你哪些命中缓存、哪些需要新取（并按 50 只切好批）
    ingest  把 get_fund_price_indicators 的返回存盘后写进缓存
    status  看当前缓存状态

典型用法：
    python scripts/price_cache.py plan --codes-from inflow.json outflow.json \
        --trade-date 20261023 --cache-dir cache
    # 拿到 BATCH 行 → 调接口 → 把返回存成 price1.json / price2.json
    python scripts/price_cache.py ingest price1.json price2.json --cache-dir cache
"""

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wind_io import BATCH_SIZE, PCT_FIELDS, PRICE_INDEXES, codes_of, num, to_records  # noqa: E402


def cache_path(cache_dir, trade_date):
    return os.path.join(cache_dir, "price_%s.json" % trade_date)


def latest_cached_date(cache_dir):
    files = sorted(glob.glob(os.path.join(cache_dir, "price_*.json")))
    return os.path.basename(files[-1])[6:-5] if files else None


def load_cache(cache_dir, trade_date):
    p = cache_path(cache_dir, trade_date)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save_cache(cache_dir, trade_date, data):
    os.makedirs(cache_dir, exist_ok=True)
    with open(cache_path(cache_dir, trade_date), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=0)


def cmd_plan(args):
    if args.codes_from:
        recs = []
        for p in args.codes_from:
            recs += to_records(p)
        codes = codes_of(recs)
    elif args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        sys.exit("需要 --codes 或 --codes-from")

    trade_date = args.trade_date
    if trade_date in (None, "", "auto"):
        trade_date = latest_cached_date(args.cache_dir)
        if not trade_date:
            sys.exit("缓存为空，请用 --trade-date 指定最新交易日（如 20261023）")
        print("提示：未指定 --trade-date，沿用缓存里最近的交易日 %s；若已跨日请重取" % trade_date)

    cache = load_cache(args.cache_dir, trade_date)
    # 均价缺失的不算命中
    miss = [c for c in codes if not (cache.get(c) or {}).get("avg")]
    hit = len(codes) - len(miss)

    print("交易日 %s｜代码 %d 只｜缓存命中 %d｜需新取 %d" % (trade_date, len(codes), hit, len(miss)))
    if not miss:
        print("全部命中，无需调用行情接口。")
        return
    for i in range(0, len(miss), BATCH_SIZE):
        batch = miss[i:i + BATCH_SIZE]
        print("BATCH %d (%d只): %s" % (i // BATCH_SIZE + 1, len(batch), ",".join(batch)))
    print("建议 indexes: %s" % PRICE_INDEXES)


def cmd_ingest(args):
    total_new = 0
    by_date = {}
    for path in args.files:
        for rec in to_records(path):
            code = rec.get("Wind代码") or rec.get("代码")
            if not code:
                continue
            td = str(rec.get("最新交易日") or args.trade_date or "").strip()
            if not td:
                sys.exit("%s 缺少「最新交易日」字段，请用 --trade-date 指定" % path)
            by_date.setdefault(td, {})[str(code)] = {
                "name": rec.get("中文简称") or rec.get("证券简称") or str(code),
                "avg": num(rec.get("最新均价")),
                "trade_date": td,
                "pct": {f: num(rec.get(f)) for f in PCT_FIELDS},
            }
            total_new += 1

    for td, items in by_date.items():
        cache = load_cache(args.cache_dir, td)
        cache.update(items)
        save_cache(args.cache_dir, td, cache)
        print("写入 %s：本次 %d 条，缓存累计 %d 条" % (cache_path(args.cache_dir, td), len(items), len(cache)))
    print("共处理 %d 条" % total_new)


def cmd_status(args):
    files = sorted(glob.glob(os.path.join(args.cache_dir, "price_*.json")))
    if not files:
        print("缓存为空：%s" % args.cache_dir)
        return
    for p in files:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        filled = sum(1 for v in data.values() if v.get("avg"))
        print("%s  标的 %d 条（有均价 %d）" % (os.path.basename(p), len(data), filled))


def main():
    ap = argparse.ArgumentParser(description="行情缓存：同一交易日只取一次价")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("plan", help="报出需新取的代码并切好批")
    p1.add_argument("--codes", help="逗号分隔的 Wind 代码")
    p1.add_argument("--codes-from", nargs="+", help="从份额返回 json 里提取代码")
    p1.add_argument("--trade-date", default="auto", help="最新交易日，如 20261023")
    p1.add_argument("--cache-dir", default="cache")
    p1.set_defaults(func=cmd_plan)

    p2 = sub.add_parser("ingest", help="把行情返回写入缓存")
    p2.add_argument("files", nargs="+", help="行情接口返回的 json 文件")
    p2.add_argument("--trade-date", default=None)
    p2.add_argument("--cache-dir", default="cache")
    p2.set_defaults(func=cmd_ingest)

    p3 = sub.add_parser("status", help="查看缓存")
    p3.add_argument("--cache-dir", default="cache")
    p3.set_defaults(func=cmd_status)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
