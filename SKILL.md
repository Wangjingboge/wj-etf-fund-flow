---
name: etf-fund-flow
version: "1.2.0"
display_name: 股票ETF资金流向-望京博格版
display_name_en: Stock ETF Fund Flow (WJ Bogle Edition)
author: 望京博格
description: 股票ETF资金流向榜单。统计股票型ETF在指定周期的资金净流入/净流出排名，把「流入前N」与「流出前N」合并到一张榜单图里。使用时先让用户选时间区间（近一天/近一周/近一个月/今年以来/自定义起止日），再让用户选流入、流出各取前几名。当用户要做ETF资金流排行、资金流向复盘、小红书/公众号榜单配图，或问「哪些ETF净流入最多/流出最多/昨天哪些ETF在被买」时使用。
description_zh: 股票ETF资金流向榜单。基于 Wind 数据统计股票型ETF在指定周期的资金净流入/净流出排名，把「流入前N」与「流出前N」合并到一张可直接发布的榜单图。执行前先让用户选时间区间（近一天/近一周/近一个月/今年以来/自定义起止日），再让用户选流入、流出各取前几名。适用于ETF资金流排行、资金流向复盘、周度年度资金迁徙分析、小红书或公众号榜单配图，以及「哪些ETF净流入最多」「昨天哪些ETF在被买」这类问题。
description_en: Ranks stock ETFs by net fund inflow and outflow over a chosen period using Wind data, and renders the inflow top-N and outflow top-N together in a single publish-ready ranking chart. Before running, it asks the user for the time window (last trading day / last week / last month / year-to-date / custom date range) and how many names to show on each side. Use it for ETF fund-flow rankings, flow reviews, weekly or yearly capital-rotation analysis, and social-media or WeChat ranking visuals.
agent_created: true
---

# 股票 ETF 资金流向 · 望京博格版

> 作者：望京博格 ｜ 统计口径与榜单结构来自「望京博格」日常复盘体系

产出**一张**榜单图：上半部分是资金净流入 TOP N，下半部分是净流出 TOP N，同一张图里做对比。

> 更新 2026-11-01：更名为「股票ETF资金流向-望京博格版」，补齐 author 字段。
> 更新 2026-10-24：行情按交易日缓存、单批 50 只、流入/流出可分别设 N。

## 执行流程（第 0 步不可跳过）

### 第 0 步：先问用户，两个问题一次问完

**不管用户话里说没说清，都要问。**用 `AskUserQuestion` 一次性提两题：

**问题 1｜统计区间**（header: `统计区间`）

| 选项 | 说明 |
|---|---|
| 近一周（推荐） | 最近 5 个交易日，最常用的复盘周期 |
| 近一天 | 最近一个已收盘交易日 |
| 近一个月 | 最近 20 个交易日 |
| 今年以来 | 上年最后一个交易日至今 |

用户要指定具体日期时，会点「其他」手输，或直接在对话里说"10月8号到10月15号"，识别到就跳过选项直接用。

**问题 2｜榜单只数**（header: `前N名`）

| 选项 | 说明 |
|---|---|
| 流入流出各前 15（推荐） | 常规版，一屏拉完 |
| 流入流出各前 10 | 短榜单，配图干净 |
| 流入流出各前 20 | 覆盖更全，图偏长 |
| 两者数量不同 | 用户点「其他」说，例如"流入15、流出5" |

用户已经在原话里同时给了区间和只数，可以不问；只给了一个的，另一个仍然要问。

### 第 1 步：把周期翻译成日期

先确认今天和最近一个**已收盘**交易日（`date +"%Y-%m-%d %A"`；周末就回退到上周五），再按下表取区间。周末节假日不自己编日历，最终以 Wind 返回列名里的实际日期为准。

| 用户选择 | 起始日（份额基数日） | 结束日 |
|---|---|---|
| 近一天 | 最近已收盘交易日的**前一交易日** | 最近已收盘交易日 |
| 近一周 | 最近交易日往前数第 6 个交易日（覆盖 5 个交易日） | 最近交易日 |
| 近一个月 | 最近交易日往前数第 21 个交易日（覆盖 20 个交易日） | 最近交易日 |
| 今年以来 | **上年最后一个交易日** | 最近交易日 |
| 自定义 | 用户给的起始日的**前一交易日** | 用户给的结束日 |

起始日往前推一天，因为 Wind 的区间份额变化以起始日收盘份额为基数。

### 第 2 步：取份额变化（2 次调用，并行发）

```
筛选{起始日}至{结束日}区间内场内流通份额增加最多的50只股票型ETF
筛选{起始日}至{结束日}区间内场内流通份额减少最多的50只股票型ETF
```

- 单日周期写成 `筛选2026年10月22日场内流通份额增加最多的50只股票型ETF`
- **必须取满 50 只，不能只要 N 只**——份额变化排名 ≠ 金额排名，均价高的会插队
- 两次**并行**发出，不要串行等
- 不要试图用"份额变化最大的100只"一次拿两侧，实测该写法只按增长量排序，拿不到流出侧
- 返回原样存盘：`inflow.json` / `outflow.json`

### 第 3 步：取价格（先查缓存，只补缺口）

均价和涨跌幅**只跟交易日有关，跟统计区间无关**。所以同一交易日只取一次价，之后换任何区间都复用。

```bash
python scripts/price_cache.py plan --codes-from inflow.json outflow.json \
    --trade-date 20261023 --cache-dir cache
```

输出形如：

```
交易日 20261023｜代码 100 只｜缓存命中 100｜需新取 0
全部命中，无需调用行情接口。
```

- **需新取 0** → 直接跳到第 4 步，一次接口都不用调
- **有 BATCH 行** → 每行是一批（已按 50 只切好），逐批调 `get_fund_price_indicators`，
  `indexes` 用脚本打印的「建议 indexes」（一次带全 5 个涨跌幅字段，换周期不用重取）
- 每批返回按 `price1.json` / `price2.json` 存盘，然后写回缓存：

```bash
python scripts/price_cache.py ingest price1.json price2.json --cache-dir cache
```

`indexes` **必须带全 5 个涨跌幅字段**。只取其中一两个会让缓存字段残缺，换周期时 `--pct-field` 取不到值、图上整列变成 "-"。补全办法：重新对该批代码取一次全字段，再 `ingest` 覆盖。

缓存按交易日分区（`cache/price_20261023.json`），换交易日不会串。`--trade-date` 与份额查询的结束日保持一致。

实测覆盖率：本周榜单 100 只已缓存，换成近一个月榜单后 **64 只命中、36 只需补取**（一批就能取完）。也就是说同一天换区间，行情接口从 2 批降到 1 批，甚至 0 批。

### 第 4 步：组装 raw.json

不要手写数据，脚本按 Wind 代码自动对齐：

```bash
python scripts/build_raw.py \
  --inflow inflow.json --outflow outflow.json \
  --price-cache cache --pct-field 5日涨跌幅 --pct-label 周涨跌幅 \
  --out raw.json \
  --period-label "周度资金流 · 2026/10/19-10/23" \
  --title "本周ETF：钱去哪了" \
  --subtitle "创业板一周跌3.1%，它的ETF却被买了203亿" \
  --insight "净流入前9名清一色宽基，4只沪深300一周吸金603亿；" "半导体设备5只产品合计被赎回35.7亿份，是全周失血最重的赛道。"
```

`--pct-field` 对应周期：近一天 `涨跌幅`、近一周 `5日涨跌幅`、近一个月 `20日涨跌幅`、今年以来 `年初至今涨跌幅`、自定义区间加 `--hide-pct`。

脚本会报告行数与"没取到均价被剔除"的代码。若提示涨跌幅全为空，说明 `--pct-field` 与缓存字段对不上。

### 第 5 步：出图（一张图）

```bash
python scripts/draw_rank.py --input raw.json --out ETF资金流向.png --top-in 15 --top-out 15
```

| 参数 | 作用 |
|---|---|
| `--top-in N` / `--top-out N` | 流入、流出各自取前几名；`--top N` 是两侧同值简写 |
| `--only inflow` / `outflow` | 只画一侧，默认 both（同一张图） |
| `--pct-label ""` | 隐藏涨跌幅列 |
| `--min-height 1440` | 行数少时补到指定高度（发小红书 3:4 用） |

画布宽固定 1080，高度随行数自适应，各前 15 约 1900px。

### 复用规则（避免重复取数）

| 用户新要求 | 该做什么 |
|---|---|
| 只改 N（前15 改成前30） | **不取数**，直接 `draw_rank.py --input raw.json --top-in 30` 重画 |
| 只改标题/署名/样式 | **不取数**，同上重画 |
| 同一天换区间（近一周 → 近一个月） | 份额重取 2 次；价格**命中缓存，0 次** |
| 换交易日 | 全部重取，缓存自动落到新日期文件 |
| 同一区间再问一次 | 若 `raw.json` 还在，直接重画 |

## 数据口径（固定，不允许改写）

```
净流入(亿元) = 区间内场内流通份额变化(亿份) × 区间成交均价(元)
```

- 只统计**股票型 ETF**，不含跨境、商品、债券、货币 ETF
- 红涨绿跌：净流入红色，净流出绿色（A 股习惯，别用美股配色）
- 均价默认取区间**最后一个交易日**的成交均价作近似；要精确就改区间 VWAP，见 `references/data-workflow.md`
- 不要拿东财"主力净流入"当资金流入，那是二级市场博弈数据

## 交付前自检

1. **金额排序**：按金额降序，不是份额变化降序（脚本已处理，抽查第 1 名）
2. **量级校验**：挑 1-2 只对 `references/data-workflow.md` 的回归基准或第三方数据，偏差超 1% 就查是不是均价取错交易日
3. **方向合理性**：流入前排通常是宽基；全是小盘/行业且金额巨大，多半错行
4. **文案自洽**：`insight` 里的"前 9 名都是宽基""4 只沪深300 合计 603 亿"必须现算一遍，不能凭印象
5. **一张图**：流入流出在同一张 PNG 里，不拆两张
6. **脚注**：保留口径说明 + "不构成投资建议"

## 附带产物

用户要发小红书/公众号时，再给 3-5 行文案 + 话题标签，突出两个对比：流入龙头是谁、流出最狠的是哪个赛道。

## 参考

- `references/data-workflow.md`：Wind 字段细节、50 只上限、精确 VWAP、常见坑、**回归校验基准**
- `scripts/price_cache.py`：行情缓存（plan / ingest / status），一个交易日只取一次价
- `scripts/build_raw.py`：份额 + 价格 → raw.json，按代码对齐
- `scripts/draw_rank.py`：raw.json → 榜单图
- `scripts/wind_io.py`：Wind 返回结构解析、批次大小、涨跌幅字段清单
- `scripts/sample_data.json`：回归样本（2026/10/19-10/23 真实 100 只），改脚本后先拿它验一遍

## 运行环境

- Python 需装 Pillow。本机若 `python` 不在 PATH，用
  `C:\Users\99388\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- 中文字体默认走 `C:/Windows/Fonts/msyhbd.ttc`，缺失时在 `draw_rank.py` 的 `FONT_CANDIDATES` 里补路径
- 缓存目录建议放在**当前工作区**的 `cache/`，不要写进 Skills 目录，避免跨项目串数据

## 已知边界

- 单次份额查询上限约 50 行，`N > 50` 时只能取到 50 只，如实告知用户不要硬凑
- 自定义区间没有对应的区间涨跌幅字段，用 `--hide-pct` 隐藏该列
- 均价是"最后一日均价近似"，长区间（今年以来）误差会放大，用户强调精确时改用区间 VWAP
- **涨跌幅缺失时绝不跨周期顶替**：`--pct-field 年初至今涨跌幅` 取不到就显示 "-"，不会拿 5日涨跌幅 冒充（这是造假）。若整列大量 "-"，回第 3 步补取全字段
- 金额统一两位小数，千亿级榜单也不取整，避免流入流出两列精度不一致
