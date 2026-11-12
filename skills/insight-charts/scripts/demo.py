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

if __name__ == "__main__":
    os.makedirs(EX, exist_ok=True)
    os.makedirs(AS, exist_ok=True)
    for name in (sys.argv[1:] or SPECS):
        spec = SPECS[name]()
        with open(os.path.join(EX, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=1)
        print(ic.render(spec, os.path.join(AS, name + ".png")))
