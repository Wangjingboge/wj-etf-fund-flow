# -*- coding: utf-8 -*-
"""Wind 返回结构的共享解析工具

MCP 工具返回有三种形态：
  1. search_funds: {"data": {"data": [{"columns": [...], "rows": [...]}]}, "error": null}
  2. price 接口:   {"data": {"columns": [...], "rows": [...]}, "error": null}
  3. 手工裁剪后的:  {"columns": [...], "rows": [...]}
"""

import json
import sys

# 一次取全所有周期要用的涨跌幅字段，避免换区间时重取
PCT_FIELDS = ["涨跌幅", "5日涨跌幅", "20日涨跌幅", "60日涨跌幅", "年初至今涨跌幅"]
PRICE_INDEXES = ",".join(["中文简称", "最新交易日", "最新均价"] + PCT_FIELDS)
BATCH_SIZE = 50  # 实测 50 只 × 8 字段可一次返回


def load_payload(path):
    with open(path, encoding="utf-8") as fh:
        obj = json.load(fh)
    if isinstance(obj, list):
        return obj
    data = obj.get("data")
    if isinstance(data, dict) and "columns" in data and "rows" in data:
        return [data]
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return data["data"]
    if "columns" in obj and "rows" in obj:
        return [obj]
    if isinstance(data, list):
        return data
    sys.exit("%s 不是可识别的 Wind 返回结构" % path)


def to_records(path):
    out = []
    for block in load_payload(path):
        names = [c["name"] if isinstance(c, dict) else str(c) for c in block["columns"]]
        for row in block["rows"]:
            out.append(dict(zip(names, row)))
    return out


def pick_change_col(rec):
    """找份额变化列：优先"份额变化"，其次"份额...增加/减少" """
    for pattern in ("份额变化",):
        keys = [k for k in rec if pattern in k]
        if keys:
            return keys[-1]
    keys = [k for k in rec if "份额" in k and ("增加" in k or "减少" in k)]
    return keys[-1] if keys else None


def num(v):
    if v is None or v == "" or v == "--":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def codes_of(records):
    """从记录里按出现顺序取 Wind 代码"""
    seen, out = set(), []
    for rec in records:
        c = rec.get("Wind代码") or rec.get("代码")
        if c and c not in seen:
            seen.add(c)
            out.append(str(c))
    return out
