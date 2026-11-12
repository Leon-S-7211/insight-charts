---
name: insight-charts
description: Draw research-report-quality charts with matplotlib in two house styles (deep-teal data-vendor style, greyscale sell-side style). Use whenever the user asks for a chart, figure, plot, 图表, 画图, 配图, 可视化, or wants data in a report, deck or article to look professional — trend lines with event dividers, family-coloured stacked bars, bar+line combos, 2x2 panel grids, scenario fans with a value-driver table, capability ladders with stage icons, stacked areas with one highlighted layer, phase charts with dashed boxes and one-line verdicts, profit bridges (waterfalls), histories aligned by year of development, process flows with cost bars, structure comparisons with numbered side notes, stacked components with a total line, donut rings, flywheels and tier diagrams; plus emphasis marks (dashed box, red cross, pin, numbered dot) and era strips. Also covers when to place a chart, how to write its title and caption, and how to lay out a page that makes one point.
---

# insight-charts：研报级图表

把数据画成「一眼能读出结论」的图。本技能包含三样东西：一套配色与版式规范、十六个现成画法和一组强调记号（`scripts/insight_charts.py`）、一套「什么时候放图、标题怎么写、一页怎么排」的写作规则。

## 工作流程

1. **先定结论，再选图**。用一句话写出这张图要让读者记住什么。写不出来就先不要画，回去看数据。
2. **按下表选画法**。拿不准时读 `references/recipes.md`，每个画法都有「什么时候用、什么时候别用」。
3. **选主题**。`teal`（深青）适合数据展示、对外文章、仪表盘式内容；`mono`（灰阶加单色高亮）适合研报正文、论证型内容。同一份文档只用一个主题。
4. **写 JSON 规格或直接调 Python**，渲染出图。
5. **自查**（见文末清单），有问题改规格重画。
6. **把图放进文字里**。位置和配套文字按 `references/writing-rhythm.md`。

## 选哪个画法

| 你手上的数据和想说的话 | 画法 | 主题 |
|---|---|---|
| 多条序列随时间变化，中间有发布、政策、调价等节点 | `trend_events` | teal |
| 总量随时间增长，内部由几个「家族」的多代产品构成 | `stacked_family` | teal |
| 一个量看规模、另一个量看比率（收入与毛利率、金额与占比） | `bar_line` | 两者皆可 |
| 四个左右相互关联的小结论，想放在一屏里 | `panel_grid` | mono |
| 几层构成中只有一层是主角，其余是陪衬 | `area_highlight` | mono |
| 历史走势加乐观、基准、悲观三种未来，并要列出背后的假设数字 | `scenario_fan` | mono |
| 能力或阶段逐级跃迁，每个节点要配一句说明 | `capability_ladder` | mono |
| 一段很长的历史分成几个阶段，每段要给一句定性 | `phase_trend` | mono |
| 从一个总数拆到另一个总数，看利润或现金漏在哪 | `waterfall` | mono |
| 两家公司处在不同年代，想比「同一发展阶段」 | `aligned_compare` | mono |
| 一个流程的各环节，以及每个环节花了多少钱 | `process_cost` | mono |
| 两三个主体的结构（资产、收入、成本）对比，配编号结论 | `share_compare` | mono |
| 几项投入加起来看总量，还要和对手逐年比 | `stacked_total` | mono |
| 一个总数由哪几块构成，或者收入和利润的构成对比 | `donuts` | mono |
| 正反馈的商业逻辑：A 带来 B，B 又带来 A；可以内外两圈交错，也可以画成向外长的螺旋 | `flywheel` | mono |
| 几类业务按某个维度分层（变现难易、壁垒高低），层与层之间有流量或能力流动 | `tiers` | mono |

**强调记号**：上面大多数画法都接受 `marks`，在图上加虚线框（圈出一段）、红叉（否定一种外推）、贴线小牌（把事件贴在曲线上）、编号圆点（和旁注对应）。`trend_events` 和 `phase_trend` 还接受 `eras`，在图上方画一条「时代条」，最后一段可以带问号。mono 单图接受 `notes`，在右侧放一栏编号结论，做到图文同屏。写法见 `references/recipes.md` 的「通用参数」。

## 怎么调用

依赖只有 matplotlib。先确认字体：

```bash
python scripts/insight_charts.py --fonts     # 中文要显示 ok；否则先装 Noto Sans SC 或思源黑体
python scripts/insight_charts.py --list      # 列出画法和图标
```

**方式一：JSON 规格**（推荐，可留档、可复现）

```bash
python scripts/insight_charts.py my_chart.json -o my_chart.png
```

```json
{
  "recipe": "trend_events",
  "title": "各行业客户月度支出中位数",
  "ylabel": "客户月支出中位数（美元）", "yfmt": "$",
  "x": ["Nov-24", "Dec-24", "Jan-25"],
  "series": {"科技": [120, 180, 260], "金融": [200, 240, 410]},
  "events": [{"at": "Dec-24", "label": "新模型发布"}],
  "source": "资料来源：公司公告，作者整理"
}
```

`examples/` 里每个画法都有一份完整规格，照着改最快。`assets/` 里是对应的成品图。

**方式二：Python**

```python
import sys; sys.path.insert(0, "<本技能目录>/scripts")
import insight_charts as ic
ic.trend_events(x, series, events=[{"at": "May-25", "label": "Opus 4.5"}],
                title="…", ylabel="…", yfmt="$", source="资料来源：…", out="fig.png")
```

通用约定：
- `x` 一律是**字符串标签列表**（日期也写成字符串）。事件、标注的位置用标签名或下标指定，下标可以是小数。
- 数值缺失写 `null`（Python 里 `None`）。
- 格式代码：`"$"` `"$2"` `"%"` `"%1"` `","` `"x"`，或任意 Python 格式串如 `"{:.1f}"`。百分比按「百分数」传值：7.6% 写 `7.6`，不要写 `0.076`。
- 所有画法都接受 `title`、`source`；规格里出现画法不认识的键会直接报错并列出可用的键。
- 标题、来源过长会自动折行。也可以用 `\n` 手动指定折行位置。
- 输出后缀决定格式：`.png`（200 dpi）、`.svg`、`.pdf`。
- 每个函数的完整参数见 `references/recipes.md`。

## 不可违背的五条

1. **标题写结论，不写图名**。「毛利率保持在健康区间」可以，「毛利率走势图」不行。数据展示类的 teal 图可以用名词标题，但正文里紧挨着的那句话必须是结论。
2. **颜色有含义才上色**。mono 主题里只有主角有颜色，其余一律灰。teal 主题里同一实体在全篇所有图中颜色不变。
3. **每张图都有来源行**。自己算的写「资料来源：××，作者测算」。预测值在横轴标签加 `E`，柱子用更浅的灰（`forecast_from`）。
4. **不要把品牌标志、水印画进图里**。需要署名时只用 `brand` 参数写自己的名字。
5. **不改变数据来迁就版面**。坐标轴截断、对数轴、双轴刻度不对齐，都要在图内或来源行写明。

## 自查清单

渲染后把图片读回来看一遍，逐条核对：

- [ ] 文字没有互相压住，也没有被裁掉。事件标签、数据标签、图例、来源行各占各的位置。
- [ ] 中文没有变成方框。
- [ ] 读者不看正文，只看标题加图，能说出结论。
- [ ] 颜色数量：teal 不超过 6 条线；mono 每张图（联排时每个面板）除灰色外不超过 2 种颜色。
- [ ] 横轴标签不超过 25 个左右（用 `xtick_every` 抽稀）。
- [ ] 双轴图的图例写明了哪条看左轴、哪条看右轴（LHS / RHS，或「右轴」）。
- [ ] 来源行存在，口径与正文一致。
- [ ] 强调记号不超过两种（虚线框、短红字、高亮色里挑），每个虚线框都配了一句话说明圈的是什么。
- [ ] 数据标签只标关键点（阶段端点、首尾、主角），没有挤成一片。
- [ ] 用了编号圆点时，旁注里的编号和图上一一对应。

## 参考文件

- `references/recipes.md`：十六个画法的适用场景、参数表、通用参数（强调记号、时代条、旁注）、常见错误。
- `references/style-tokens.md`：两套主题的色值、字号、线宽、留白。要用别的绘图库复刻本风格时读它。
- `references/writing-rhythm.md`：什么时候该放图、放在哪、标题与前后文怎么写，一页怎么排、强调怎么用、哪些做法别学。
- `examples/*.json`、`assets/*.png`：规格样例与成品。
