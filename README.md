# 股票ETF资金流向 · 望京博格版

一个把「哪类 ETF 在被买、哪类在被卖」压成**一张图**的技能（Skill）。

上半部分是资金净流入 TOP N，下半部分是净流出 TOP N，同一张图里做对比，出图即可发布。

- 作者：望京博格
- 版本：1.2.0
- 数据来源：Wind
- 统计范围：仅股票型 ETF（不含跨境 / 商品 / 债券）

## 产出示例

一张 1080 宽的榜单图，包含：

- 头部标题区（区间、结论副标题）
- 净流入 TOP N 榜（含区间涨跌幅）
- 净流出 TOP N 榜
- 底部口径说明与数据来源

已实测区间：近一周、近一个月、今年以来。

## 工作流程

```
选区间 → 选N → 取份额变化 → 取行情(带缓存) → 组装 → 出图
```

### 第 0 步：先问用户（不可跳过）

每次触发都会先确认两件事，不先跑数据：

1. **统计区间**：近一天 / 近一周 / 近一个月 / 今年以来 / 自定义起止日
2. **榜单只数**：流入流出各取前几名（可分开设置，如「流入 15、流出 5」）

只有用户已把区间和只数都说明白，才跳过提问直接执行。

## 统计口径

```
净流入 = 区间场内流通份额变化 × 区间成交均价
```

- 份额变化来自 Wind 的区间查询（增加侧、减少侧各取 50 只）
- 均价为该交易日全天成交均价，是折算金额的默认价格
- 涨跌幅按区间选对应字段：5 日 / 20 日 / 60 日 / 年初至今
- 颜色遵循 A 股习惯：红涨绿跌

## 节省接口调用的三个设计

| 场景 | 无优化 | 本技能 |
|---|---|---|
| 当天首次跑 | 6 次调用 | 4 次 |
| 同一天换区间 | 6 次 | 2–3 次（行情走缓存） |
| 只改 N / 改样式 | 6 次 | 0 次（复用 raw.json 重画） |

关键点：**份额变化跟区间绑定，必须重取；均价和涨跌幅只跟交易日绑定，可以复用**。行情按交易日分区缓存（`cache/price_YYYYMMDD.json`），换区间时先算缺口，只补没命中的标的，单批 50 只。

## 目录结构

```
etf-fund-flow/
├── SKILL.md                    # 技能主文档（执行流程、参数、边界）
├── README.md
├── LICENSE
├── references/
│   └── data-workflow.md        # Wind 字段细节、常见坑、回归基准
└── scripts/
    ├── wind_io.py              # Wind 返回结构解析、批次大小、字段清单
    ├── price_cache.py          # 行情缓存：plan / ingest / status
    ├── build_raw.py            # 份额 + 行情 → raw.json
    ├── draw_rank.py            # raw.json → 榜单图
    └── sample_data.json        # 100 只真实数据的回归样本
```

## 依赖

- Python 3.9+
- Pillow（画图）
- 中文字体（默认取 `msyhbd.ttc` / `msyh.ttc`，缺失时需指定字体路径）

```bash
pip install pillow
```

## 快速试用

用内置回归样本直接出图，不依赖任何数据接口：

```bash
python scripts/draw_rank.py --input scripts/sample_data.json --out out.png --top-in 15 --top-out 15
```

预期结果：净流入合计 1370.09 亿 / 净流出合计 77.51 亿。

## 常用参数

```bash
# 两侧数量不同
python scripts/draw_rank.py --input raw.json --out out.png --top-in 20 --top-out 5

# 只看流出榜
python scripts/draw_rank.py --input raw.json --out out.png --top 10 --only outflow

# 隐藏涨跌幅列（自定义区间没有对应字段时）
python scripts/build_raw.py ... --hide-pct          # 组装阶段就不带该列
python scripts/draw_rank.py --input raw.json --out out.png --pct-label ""   # 或出图阶段传空

# 行情缓存：先看缺哪些、再写回
python scripts/price_cache.py plan --codes-from inflow.json outflow.json --trade-date 20261023 --cache-dir cache
python scripts/price_cache.py ingest price1.json --cache-dir cache
```

## 已知边界

- 单次份额查询上限约 50 行，`N > 50` 时只能取到 50 只
- 自定义区间没有对应的区间涨跌幅字段，需隐藏该列
- 均价是「最后一日均价近似」，长区间（今年以来）误差会放大；要求精确时改用区间 VWAP
- 「份额变化最大的 100 只」这类查询只按增长量排序，拿不到流出侧，所以流入 / 流出必须分两次查询

## 安装到 WorkBuddy

把 `etf-fund-flow` 整个文件夹放到 `~/.workbuddy/skills/` 下即可被识别。

## 免责声明

本工具仅用于数据整理与信息展示，不构成任何投资建议。数据可能存在延迟或误差，据此操作风险自担。
