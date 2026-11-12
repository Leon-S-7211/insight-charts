#!/usr/bin/env python3
"""Build the example specs in ../examples and render them to ../assets.

    python demo.py            # all
    python demo.py trend_events scenario_fan
All data here is made up for illustration."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import insight_charts as ic  # noqa: E402

EX = os.path.join(HERE, "..", "examples")
AS = os.path.join(HERE, "..", "assets")
rng = np.random.default_rng(7)
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def months(start_y, start_m, n, fmt="{m}-{y}"):
    out = []
    y, m = start_y, start_m
    for _ in range(n):
        out.append(fmt.format(m=MON[m - 1], y=str(y)[2:], Y=y))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def r(a, nd=1):
    return [None if v is None else round(float(v), nd) for v in a]


def spec_trend_events():
    x = months(2024, 11, 23)
    t = np.arange(23)
    grow = lambda k, s, j: np.maximum(0, k * np.exp(s * t) - k + rng.normal(0, j, 23).cumsum())  # noqa: E731
    return {
        "recipe": "trend_events",
        "title": "Median Monthly Spend by Sector",
        "ylabel": "Median Customer Spend", "yfmt": "$",
        "source": "Source: illustrative data",
        "x": x,
        "series": {
            "Tech": r(grow(60, 0.20, 25)), "Financial": r(grow(95, 0.205, 90)),
            "Consumer": r(grow(40, 0.165, 40)), "Comm. Services": r(grow(45, 0.165, 30)),
            "Energy & Industrial": r(grow(70, 0.175, 160)), "Other": r(grow(35, 0.16, 15)),
        },
        "events": [
            {"at": "May-25", "label": "Nova 4\nNova Code GA"},
            {"at": "Jul-25", "label": "Nova for\nFinancial Services"},
            {"at": "Nov-25", "label": "Atlas 4.5"},
            {"at": "Jan-26", "label": "Nova Cowork"},
            {"at": "Apr-26", "label": "Atlas 4.7"},
            {"at": "Jul-26", "label": "Atlas 5\nNova 5"},
        ],
    }


def spec_trend_events_price():
    n = 70
    x = [f"{((i * 7) // 30 + 6 - 1) % 12 + 1}/{(i * 7) % 30 + 1}/{2025 + ((i * 7) // 30 + 5) // 12}" for i in range(n)]
    walk = lambda a, b, j: np.linspace(a, b, n) + rng.normal(0, j, n).cumsum() * 0.3  # noqa: E731
    mid = walk(2.3, 0.75, 0.05)
    top = [None] * 24 + list(np.linspace(3.4, 1.0, n - 24) + rng.normal(0, 0.09, n - 24))
    new = [None] * 52 + list(np.linspace(4.2, 1.95, n - 52) + rng.normal(0, 0.16, n - 52))
    return {
        "recipe": "trend_events", "ylabel": "Price per Million Tokens", "yfmt": "$2",
        "ylim": [0, 5], "x": x, "xtick_every": 3, "chip": "ink", "chip_at": "bottom",
        "series": {"Blended Price": r(mid * 1.05 + 0.1, 2), "Mid tier": r(mid, 2), "Top tier": r(top, 2),
                   "Small tier": r(np.clip(walk(0.55, 0.6, 0.03), 0.3, 1.2), 2), "Frontier": r(new, 2)},
        "colors": ["#0D4753", "#E9B614", "#F38C5C", "#AACFD8", "#E84A47"],
        "events": [{"at": 24, "label": "Atlas 4.5"}, {"at": 52, "label": "Nova 5"}, {"at": 66, "label": "Atlas 5.5"}],
    }


def spec_stacked_family():
    n = 41
    x = [f"{1 + (3 + i * 7) // 30}/{1 + (3 + i * 7) % 30}/2026" for i in range(n)]
    t = np.arange(n)
    ramp_in = lambda s, k: np.clip((t - s) / 6, 0, 1) * k * (1 + 0.03 * (t - s))  # noqa: E731
    total = 0.5 + 7.2 * (t / (n - 1)) ** 1.15 + rng.normal(0, 0.12, n)
    son55, son5, son46 = ramp_in(38, 0.3), ramp_in(8, 0.55) * 1.4, np.clip(0.35 + 0.012 * t, 0, 1)
    son_o = np.clip(0.3 - 0.004 * t, 0.12, 1)
    op55, op5, op48 = ramp_in(36, 1.1), ramp_in(26, 1.6), ramp_in(18, 1.4) * np.clip(1.6 - 0.03 * (t - 18), 0.45, 1.6)
    haiku, fable = 0.05 + 0.002 * t, ramp_in(24, 0.22)
    other = np.clip(t - 28, 0, 1) * 0.1
    mythos = np.where((t == 30) | (t == 31), 0.18, 0.0)
    used = son55 + son5 + son46 + son_o + op55 + op5 + op48 + haiku + fable + other + mythos
    op_o = np.clip(total - used, 0.05, None)
    return {
        "recipe": "stacked_family", "ylabel": "Observed Weekly Spend ($M)", "yfmt": "$",
        "source": "Source: illustrative data",
        "x": x, "xtick_every": 3,
        "layers": {"Sonnet 5.5": r(son55, 2), "Sonnet 5": r(son5, 2), "Sonnet 4.6": r(son46, 2),
                   "Other Sonnet": r(son_o, 2), "Opus 5.5": r(op55, 2), "Opus 5": r(op5, 2),
                   "Opus 4.8": r(op48, 2), "Other Opus": r(op_o, 2), "Haiku": r(haiku, 2),
                   "Fable": r(fable, 2), "Mythos": r(mythos, 2), "Other": r(other, 2)},
        "families": {"Sonnet": ["Sonnet 5.5", "Sonnet 5", "Sonnet 4.6", "Other Sonnet"],
                     "Opus": ["Opus 5.5", "Opus 5", "Opus 4.8", "Other Opus"]},
        "minor": ["Haiku", "Fable", "Mythos", "Other"],
    }


def spec_bar_line_teal():
    x = months(2024, 11, 23)
    t = np.arange(23)
    med = 0.02 * np.exp(0.225 * t)
    return {"recipe": "bar_line", "theme": "teal", "title": "Top 1% Spend & Spend Share",
            "x": x, "bars": r(30 + 0.7 * t + rng.normal(0, 3.5, 23)), "line": r(med, 2),
            "left_fmt": "%", "right_fmt": "$2", "ylabel": "% of Combined Spend",
            "right_label": "Median Spend ($M)", "bar_name": "Top 1% as a Percent of Combined Spend (LHS)",
            "line_name": "Top 1% Median Spend (RHS)", "left_ylim": [0, 100]}


def spec_panel_grid():
    yrs = ["2022", "2023", "2024", "2025"]
    return {"recipe": "panel_grid", "start_number": 15, "panels": [
        {"kind": "cost_steps", "title": "COGS breakdown – Company A vs. Company B",
         "source": "Source: Company data. Note: illustrative figures.",
         "parts": ["Labour costs", "Computing service fee", "Others"],
         "groups": {"Company B": [1, 93, 6], "Company A": [39, 38, 23]}, "highlight": "Company A"},
        {"kind": "bar_line", "title": "Company A maintains healthy GPM for on-premise deployment business",
         "source": "Source: Company data", "x": yrs, "bars": [29, 77, 174, 260.7],
         "line": [53.6, 68.2, 66.0, 48.8], "line_fmt": "%1", "right_fmt": "%", "right_ylim": [0, 80],
         "left_ylim": [0, 300], "bar_name": "Gross profit", "line_name": "Gross margin (RHS)"},
        {"kind": "bar_line", "title": "Company A's DSO trend during 2022-25", "unit": "Unit: RMB m",
         "source": "Source: Company data", "x": yrs, "bars": [57, 125, 312, 724],
         "line": [42.1, 23.1, 106.5, 152.8], "line_fmt": "{:.1f}", "right_fmt": ",", "right_ylim": [0, 180],
         "left_ylim": [0, 800], "bar_name": "Trade receivables", "line_name": "DSO (days, RHS)",
         "legend": "bottom"},
        {"kind": "bar_line", "title": "Company A's credit loss coverage ratio remained stable",
         "unit": "Unit: RMB mn", "source": "Source: Company data", "x": yrs, "bars": [0.1, 1.0, 9.0, 36.0],
         "bar_fmt": "{:.1f}", "line": [0.4, 11.1, 9.0, 10.6], "line_fmt": "%1", "right_fmt": "%",
         "right_ylim": [0, 12], "left_ylim": [0, 40], "bar_name": "Total loss allowance",
         "line_name": "Credit loss coverage ratio (RHS)", "legend": "bottom"},
    ]}


def spec_area_highlight():
    x = [f"{d:02d}-{m}-2026" for m, days in (("Feb", range(11, 29)), ("Mar", range(1, 12))) for d in days]
    n = len(x)
    main = np.array([20, 55, 110, 185, 262, 155, 96, 103, 113, 110, 104, 112, 118, 116, 88, 45, 40, 38,
                     46, 55, 59, 50, 37, 34, 30, 31, 39, 40, 38])[:n]
    return {"recipe": "area_highlight", "number": 22, "title": "Model X token usage trend on a public router",
            "source": "Source: public router data", "x": x, "xtick_every": 2,
            "layers": {"Model X-5": r(main), "Model X-4.7": r(main * 0.1 + 6), "X-4.7-Flash": r(np.full(n, 2.5)),
                       "Model X-4.5": r(np.where((np.arange(n) > 6) & (np.arange(n) < 16), 5, 3))},
            "annotation": {"at": 0, "text": "Announced 30%\nprice hike on Coding\nPlan", "y": 8}}


def spec_scenario_fan():
    h = 300 + np.concatenate([rng.normal(2, 9, 18).cumsum(), 60 + rng.normal(22, 30, 30).cumsum()])
    h = h / h[-1] * 891
    return {"recipe": "scenario_fan", "name": "Company A - 0000.HK Price", "now_label": "HKD 891.0\n17 Apr",
            "history": r(h), "now": 891, "base": 1160, "upside": 1384, "downside": 650,
            "table_title": "Value drivers\n(2026E)", "source": "Source: illustrative estimates",
            "table": {"columns": ["Total rev", "On-premise\ndeployment rev", "Open platform\nand API rev", "GPM", "Adjusted OPM"],
                      "row_labels": {"upside": "HK$1,384 upside", "base": "HK$1,160 base", "downside": "HK$650 downside"},
                      "rows": {"upside": ["Rmb5,443m", "Rmb1,175m", "Rmb4,268m", "40%", "-120%"],
                               "base": ["Rmb3,208m", "Rmb1,007m", "Rmb2,200m", "33%", "-161%"],
                               "downside": ["Rmb2,313m", "Rmb801m", "Rmb1,512m", "30%", "-240%"]}}}


def spec_capability_ladder():
    tl = [f"{MON[m]}-{y}" for y in range(2022, 2027) for m in range(0, 12, 2)][:29]
    return {"recipe": "capability_ladder", "number": 5, "source": "Source: Company data",
            "title": "Company A's model iteration is in line with the five paradigms",
            "timeline": tl,
            "stages": [{"label": "Chatbot", "icon": "chat", "y": 0}, {"label": "AI Coding Assistant", "icon": "list", "y": 1.7},
                       {"label": "Vibe Coding", "icon": "coder", "y": 3.5}, {"label": "Agentic Engineering", "icon": "network", "y": 5.4},
                       {"label": "Long Horizon Task", "icon": "timer", "y": 7.3}, {"label": "Autonomous OS", "icon": "screen", "y": 10.0}],
            "curve": [[0, 0.05], [4, 0.2], [8, 0.5], [12, 0.95], [16, 1.6], [19, 2.5], [21, 3.5], [22.5, 4.4],
                      [23.6, 5.1], [24.6, 5.9], [26, 7.1], [27.2, 8.3], [28, 9.4]],
            "milestones": [
                {"at": 4.4, "name": "CoderX1"}, {"at": 9.4, "name": "CoderX2"}, {"at": 12.4, "name": "CoderX3"},
                {"at": 15.4, "name": "CoderX4"},
                {"at": 5.8, "name": "", "note": "**Coding assistants** based on the base model", "text": [2.6, 2.7], "width": 1.9},
                {"at": 21, "name": "M-4.5:", "note": "First model to integrate native fusion of **reasoning, coding and agent** capabilities in one architecture", "text": [7.3, 5.5], "width": 1.85},
                {"at": 22.6, "name": "M-4.6:", "note": "200K **long context window** + improving coding capabilities in real life scenario", "text": [22.9, 2.75], "width": 1.5},
                {"at": 24.3, "name": "M-4.7:", "note": "long-horizon planning + tool orchestration", "text": [12.9, 6.35], "width": 1.7},
                {"at": 24.9, "name": "M-5:", "note": "A leap into **agentic engineering** for end-to-end software engineering", "text": [13.1, 8.0], "width": 1.85},
                {"at": 25.8, "name": "M-5-Turbo:", "note": "First foundation model deeply optimized for the **agent** scenario", "text": [16.6, 9.1], "width": 1.85},
                {"at": 26.9, "name": "M-5.1:", "note": "Can operate continuously and autonomously for up to **8 hours** in a single task.", "text": [22.7, 10.95], "width": 1.7},
            ]}


def spec_zh_trend_events():
    s = spec_trend_events()
    s.update(title="各行业客户月度支出中位数", ylabel="客户月支出中位数", unit="单位：美元",
             source="资料来源：示意数据")
    names = ["科技", "金融", "消费", "通信服务", "能源与工业", "其他"]
    s["series"] = dict(zip(names, s["series"].values()))
    s["events"] = [{"at": "May-25", "label": "新模型 4\n编程工具上线"}, {"at": "Nov-25", "label": "旗舰版 4.5"},
                   {"at": "Jan-26", "label": "协作版发布"}, {"at": "Jul-26", "label": "旗舰版 5"}]
    return s


def spec_zh_panel_grid():
    yrs = ["2022", "2023", "2024", "2025", "2026E", "2027E"]
    return {"recipe": "panel_grid", "start_number": 1, "panels": [
        {"kind": "bars", "title": "预计 2025-27 年本地化部署收入复合增速 81%", "unit": "单位：百万元",
         "source": "资料来源：公司公告，示意数据", "x": yrs, "values": [55, 113, 264, 534, 1007, 1753],
         "forecast_from": "2026E", "note": "2022-25 年复合增速：+114%\n2025-27E 复合增速：+81%"},
        {"kind": "bar_line", "title": "毛利率保持在健康区间", "source": "资料来源：公司公告，示意数据",
         "x": yrs[:4], "bars": [29, 77, 174, 260.7], "line": [53.6, 68.2, 66.0, 48.8], "line_fmt": "%1",
         "right_fmt": "%", "right_ylim": [0, 80], "left_ylim": [0, 300], "bar_name": "毛利（百万元）",
         "line_name": "毛利率（右轴）"},
    ]}


SPECS = {"trend_events": spec_trend_events, "trend_events_price": spec_trend_events_price,
         "stacked_family": spec_stacked_family, "bar_line_teal": spec_bar_line_teal,
         "panel_grid": spec_panel_grid, "area_highlight": spec_area_highlight,
         "scenario_fan": spec_scenario_fan, "capability_ladder": spec_capability_ladder,
         "zh_trend_events": spec_zh_trend_events, "zh_panel_grid": spec_zh_panel_grid}

# ---- 0.2.0: phases, bridges, aligned histories, process costs, structure links, marks ----
def spec_zh_phase_trend():
    yrs = [str(y) for y in range(2000, 2026)]
    t = np.arange(26)
    gross = 18 + 0.25 * t + np.where(t > 16, (t - 16) * 1.9, 0) + rng.normal(0, 0.6, 26)
    ebitda = np.concatenate([np.linspace(-38, -4, 8), np.linspace(-1, 4.5, 9), np.linspace(5, 13, 9)])
    net = np.concatenate([np.linspace(-46, -9, 8), np.linspace(-6, 2.5, 9), np.linspace(2, 7.5, 9)])
    ebitda += rng.normal(0, 1.2, 26)
    net += rng.normal(0, 1.4, 26)
    return {
        "recipe": "phase_trend", "number": 1, "yfmt": "%",
        "title": "利润率走过三个阶段：先跑通模式，再换规模，最后靠结构改善把净利率稳定转正",
        "source": "资料来源：示意数据",
        "x": yrs,
        "series": {"毛利率": r(gross), "EBITDA 利润率": r(ebitda), "净利率": r(net)},
        "phases": [
            {"from": "2000", "to": "2007", "name": "第一阶段（2000-2007）：", "verdict": "跑通模式",
             "notes": ["自营起家，先做流量", "规模效应还没出现，连年亏损"]},
            {"from": "2008", "to": "2016", "name": "第二阶段（2008-2016）：", "verdict": "以价换量",
             "notes": ["开放平台，毛利率小幅抬升", "利润再投入，净利率从负值回到零附近"]},
            {"from": "2017", "to": "2025", "name": "第三阶段（2017-2025）：", "verdict": "结构改善",
             "notes": ["高毛利业务占比上升", "净利率稳定转正"]},
        ],
        "marks": [{"type": "pin", "at": "2004", "series": "毛利率", "text": "上市", "dy": -22}],
    }


def spec_zh_waterfall():
    return {
        "recipe": "waterfall", "number": 2, "unit": "单位：亿元",
        "title": "新业务亏损吃掉主业近三成利润",
        "source": "资料来源：示意数据，作者测算",
        "steps": [
            {"label": "主业 EBIT", "value": 180, "kind": "total", "tag": "利润率 2.4%"},
            {"label": "新业务亏损", "value": -52},
            {"label": "总部费用", "value": -15},
            {"label": "投资收益", "value": 8},
            {"label": "集团 EBIT", "kind": "subtotal", "tag": "利润率 1.6%"},
        ],
        "highlight": "新业务亏损",
        "notes": ["主业利润率 2.4%，与同行相当", "新业务亏损 52 亿元，约占主业利润 29%，是最大的拖累",
                  "剔除新业务后，集团利润率可回到 2% 以上"],
        "notes_title": "利润从哪里漏掉",
    }


def spec_zh_aligned():
    return {
        "recipe": "aligned_compare", "number": 3, "yfmt": "%", "xlabel": "第{n}年",
        "title": "按发展年份对齐：B 公司前五年增速远高于 A 公司同期，第六年起差距收窄到 5 个百分点以内",
        "source": "资料来源：示意数据。注：横轴为各自统计起点后的第 N 年，虚线为预测",
        "series": {
            "B 公司": {"start": 2016, "values": [66, 58, 47, 41, 36, 33, 31, 30, 29, 28],
                       "forecast_from": 2024},
            "A 公司": {"start": 2003, "values": [26, 31, 23, 26, 39, 29, 27, 26, 25, 24]},
        },
    }


def spec_zh_process_cost():
    steps = [("顾客下单", 8.5, "支付手续费"), ("订单处理", 7.2, "IT 与折旧"), ("仓储", 11.6, "仓库租金"),
             ("拣货打包", 17.9, "仓内人工"), ("干线运输", 15.4, "干线运输"), ("末端配送", 33.8, "配送人工"),
             ("签收售后", 5.6, "客服人工")]
    return {
        "recipe": "process_cost", "number": 4, "unit": "占履约成本比例",
        "title": "末端配送占履约成本三分之一，是下一步降本的重点",
        "source": "资料来源：示意数据，作者整理",
        "steps": [{"label": a, "cost": b, "cost_label": c} for a, b, c in steps],
        "groups": [{"from": "仓储", "to": "拣货打包", "text": "仓内环节 29.5%"}],
        "highlight": "末端配送", "highlight_text": "降本空间最大",
    }


def spec_zh_share_compare():
    return {
        "recipe": "share_compare", "number": 5,
        "title": "A 公司更重固定资产，B 公司把更多资产放在股权投资上",
        "source": "资料来源：示意数据",
        "parts": ["现金", "应收", "存货", "固定资产", "股权投资", "其他"],
        "columns": {"A 公司 2015": [30, 8, 16, 28, 4, 14], "B 公司 2025": [36, 6, 18, 12, 18, 10]},
        "highlight": ["固定资产", "股权投资"],
        "numbers": {"现金": 1, "存货": 2, "固定资产": 3, "股权投资": 4},
        "notes": ["两家账上都留着三成以上现金", "存货占比接近，差别不在周转",
                  "A 公司固定资产占 28%，是 B 公司的两倍多", "B 公司股权投资占 18%，靠投资延伸生态"],
        "notes_title": "资产结构对比",
    }


def spec_zh_trend_eras():
    q = [f"{y}Q{k}" for y in range(2012, 2027) for k in range(1, 5)][:58]
    t = np.arange(58)
    trough = -10 * np.exp(-((t - 27.5) / 3.2) ** 2)              # 2018Q2-2019Q2 dip
    pe = 32.5 + 2.2 * np.sin(t / 4.5) + trough + rng.normal(0, 0.9, 58)
    ev = pe * 0.55 + rng.normal(0, 0.6, 58)
    return {
        "recipe": "trend_events",
        "title": "零售主业的估值中枢在 30-35 倍",
        "source": "资料来源：示意数据",
        "x": q, "xtick_every": 4, "yfmt": "{:.0f}x", "ylim": [0, 50],
        "series": {"市盈率（未来 12 个月）": r(pe), "EV/EBITDA（未来 12 个月）": r(ev)},
        "eras": [{"from": "2012Q1", "label": "零售期"}, {"from": "2017Q1", "label": "云业务期"},
                 {"from": "2023Q1", "label": "广告期？", "open": True}],
        "marks": [{"type": "box", "from": "2018Q1", "to": "2019Q3", "y": [8, 31],
                   "text": "估值底部", "text_at": "bottom"}],
    }


def spec_zh_share_cross():
    yrs = ["2019", "2020", "2021", "2022", "2023E", "2024E", "2025E"]
    return {
        "recipe": "stacked_family", "percent": True,
        "title": "前四大平台成交额份额",
        "source": "资料来源：示意数据。2023E 起为线性外推",
        "x": yrs,
        "layers": {"甲": [72, 68, 63, 58, 54, 50, 46], "乙": [20, 21, 22, 22, 22, 22, 22],
                   "丙": [5, 8, 11, 15, 18, 21, 24], "丁": [3, 3, 4, 5, 6, 7, 8]},
        "colors": {"甲": "#0D4753", "乙": "#AACFD8", "丙": "#F38C5C", "丁": "#C9AEAB"},
        "marks": [{"type": "cross", "from": "2023E", "to": "2025E", "text": "份额线性外推不成立"}],
    }


SPECS.update(zh_phase_trend=spec_zh_phase_trend, zh_waterfall=spec_zh_waterfall,
             zh_aligned=spec_zh_aligned, zh_process_cost=spec_zh_process_cost,
             zh_share_compare=spec_zh_share_compare, zh_trend_eras=spec_zh_trend_eras,
             zh_share_cross=spec_zh_share_cross)


def spec_zh_cycle_panels():
    q = ["1Q18", "2Q18", "3Q18", "4Q18", "1Q19", "2Q19", "3Q19", "4Q19"]
    return {"recipe": "panel_grid", "start_number": 6, "panels": [
        {"kind": "bar_line", "title": "收入增速连续四个季度放缓，2019 年下半年回到 25% 以上",
         "unit": "单位：亿元", "source": "资料来源：示意数据",
         "x": q, "bars": [1000, 1220, 1040, 1350, 1210, 1500, 1350, 1700],
         "line": [33, 31, 25, 22, 21, 23, 29, 26], "line_fmt": "%", "right_fmt": "%",
         "bar_name": "收入", "line_name": "同比增速（右轴）",
         "marks": [{"type": "box", "from": "3Q18", "to": "1Q19", "text": "下行期"}]},
        {"kind": "lines", "title": "净利率从 2019 年起连续超出一致预期",
         "source": "资料来源：示意数据", "x": q, "yfmt": "%1",
         "series": {"实际净利率": [1.2, 0.8, 0.5, -0.6, 1.5, 2.1, 2.6, 2.4],
                    "一致预期": [1.0, 0.9, 0.7, 0.2, 0.9, 1.4, 1.8, 2.0]},
         "marks": [{"type": "box", "from": "1Q19", "to": "4Q19", "text": "恢复期"}]},
    ]}


SPECS.update(zh_cycle_panels=spec_zh_cycle_panels)


# ---- 0.3.0: concept diagrams, rings, stacked totals ----
def spec_zh_flywheel():
    return {
        "recipe": "flywheel", "number": 8,
        "title": "三个飞轮互相加速：流量带来规模，规模带来现金，现金再投进会员权益",
        "source": "资料来源：作者整理",
        "wheels": [
            {"title": "收入增长：", "key": "流量飞轮", "center": "增长", "dashed": True,
             "nodes": ["更低成本", "更低价格", "更好体验", "更多流量", "更多商家", "更多选品"],
             "caption": "规模越大，成本越低"},
            {"title": "现金流增长：", "key": "资本飞轮", "center": "规模",
             "nodes": ["更快周转", "更多现金", "更多投入", "更低成本"],
             "caption": "现金流越好，融资越容易"},
            {"title": "用户增长：", "key": "会员飞轮", "center": "留存",
             "nodes": ["会员权益", "购买频次", "数据积累", "精准推荐"],
             "caption": "权益越多，用户越离不开"},
        ],
    }


def spec_zh_tiers():
    return {
        "recipe": "tiers", "number": 9,
        "title": "越靠近流量的业务越容易变现，越往下越依赖运营和重投入",
        "source": "资料来源：作者整理。注：规模为市场体量的量级示意",
        "trend": "越往下，变现越难",
        "highlight": "电商",
        "levels": [
            {"label": "第一层", "side": "易变现",
             "items": [{"name": "搜索", "note": "流量广告", "size": "千亿级"},
                       {"name": "游戏", "note": "虚拟道具", "size": "千亿级"},
                       {"name": "短视频", "note": "流量广告", "size": "千亿级"}]},
            {"label": "第二层", "side": "重运营",
             "items": [{"name": "电商", "note": "佣金＋广告", "size": "万亿级"},
                       {"name": "本地生活", "note": "佣金＋广告", "size": "千亿级"}]},
            {"label": "第三层", "side": "重运营＋重投入",
             "items": [{"name": "云服务", "note": "基础设施服务", "size": "千亿级"},
                       {"name": "物流", "note": "基础设施服务", "size": "千亿级"}]},
        ],
    }


def spec_zh_donuts():
    return {
        "recipe": "donuts", "number": 10,
        "title": "服务收入只占 15%，却贡献了近一半毛利",
        "source": "资料来源：示意数据",
        "highlight": "服务收入",
        "rings": [
            {"subtitle": "收入构成", "parts": ["商品销售", "服务收入"], "values": [85, 15], "center": "收入"},
            {"subtitle": "毛利构成", "parts": ["商品销售", "服务收入"], "values": [52, 48], "center": "毛利"},
        ],
    }


def spec_zh_sotp_panels():
    return {"recipe": "panel_grid", "start_number": 11, "ncols": 2, "panels": [
        {"kind": "donut", "title": "零售业务贡献六成收入", "source": "资料来源：示意数据",
         "parts": ["零售", "物流", "健康", "科技", "其他"], "values": [61, 17, 9, 8, 5],
         "highlight": "零售", "center": "收入\n构成"},
        {"kind": "waterfall", "title": "分部估值合计 950 亿美元，零售占一半以上", "unit": "单位：亿美元",
         "source": "资料来源：示意数据，作者测算",
         "steps": [{"label": "零售", "value": 520}, {"label": "物流", "value": 110},
                   {"label": "健康", "value": 70}, {"label": "科技", "value": 40},
                   {"label": "投资", "value": 60}, {"label": "净现金", "value": 150},
                   {"label": "合计", "kind": "subtotal"}],
         "highlight": "零售"},
    ]}


def spec_zh_stacked_total():
    y = [f"第{n}年" for n in range(1, 11)]
    return {
        "recipe": "stacked_total", "number": 13, "yfmt": "%", "total_fmt": "%1",
        "title": "按发展年份对齐，A 公司每年的长期投入占收入 8.5%-13%，是 B 公司的两倍以上",
        "source": "资料来源：示意数据。注：长期投入＝研发＋折旧摊销＋股权激励，占当年收入比例",
        "x": y,
        "groups": {
            "A 公司": {"研发": [5, 5.5, 6, 6.2, 6.5, 6.8, 7, 7.2, 7.5, 8],
                       "折旧摊销": [2.5, 2.6, 2.7, 2.8, 2.9, 3, 3, 3.1, 3.2, 3.3],
                       "股权激励": [1, 1.1, 1.2, 1.2, 1.3, 1.4, 1.4, 1.5, 1.6, 1.7]},
            "B 公司": {"研发": [1.5, 1.8, 2, 2.2, 2.4, 2.5, 2.6, 2.8, 2.9, 3],
                       "折旧摊销": [1.2, 1.3, 1.4, 1.5, 1.5, 1.6, 1.7, 1.7, 1.8, 1.9],
                       "股权激励": [0.8, 0.8, 0.9, 0.9, 1, 1, 1, 1.1, 1.1, 1.2]},
        },
    }


SPECS.update(zh_flywheel=spec_zh_flywheel, zh_tiers=spec_zh_tiers, zh_donuts=spec_zh_donuts,
             zh_sotp_panels=spec_zh_sotp_panels, zh_stacked_total=spec_zh_stacked_total)


if __name__ == "__main__":
    os.makedirs(EX, exist_ok=True)
    os.makedirs(AS, exist_ok=True)
    for name in (sys.argv[1:] or SPECS):
        spec = SPECS[name]()
        with open(os.path.join(EX, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=1)
        print(ic.render(spec, os.path.join(AS, name + ".png")))
