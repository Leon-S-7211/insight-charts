#!/usr/bin/env python3
"""insight_charts — research-grade chart recipes on top of matplotlib.

Two themes, sixteen recipes, shared emphasis marks. Import it, or drive it with a JSON spec:

    python insight_charts.py spec.json -o chart.png

Only dependency: matplotlib (numpy comes with it).
"""
from __future__ import annotations

import argparse
import inspect
import json
import re
import sys
import textwrap
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
from matplotlib import patheffects as pe  # noqa: E402
from matplotlib.transforms import blended_transform_factory  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, to_rgb  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import (Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, Patch,  # noqa: E402
                                Polygon, Rectangle)
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

__version__ = "0.4.0"

# --------------------------------------------------------------------------
# Style tokens
# --------------------------------------------------------------------------
TEAL = {
    "name": "teal",
    "ink": "#0D4753",          # titles, lead series
    "tick": "#606060",
    "label": "#555555",
    "legend": "#444444",
    "grid": "#EAEAEA",
    "event": "#A3A3A3",
    "chip_edge": "#D9D9D9",
    "series": ["#0D4753", "#AACFD8", "#F38C5C", "#1D886A", "#E9B614", "#E84A47"],
    "bar": "#AACFD8",
    "bar_edge": "#9CBEC7",
    "bar_soft": "#DEF0F0",
}
MONO = {
    "name": "mono",
    "ink": "#000000",
    "tick": "#262626",
    "tick_soft": "#8C8C8C",
    "label": "#262626",
    "legend": "#262626",
    "grid": "#E3E3E3",
    "rule": "#BFBFBF",
    "greys": ["#CCCCCC", "#B0B0B0", "#808080", "#595959"],
    "line": "#7F7F7F",
    "highlight": "#CDD8F3",    # the one coloured layer / bar
    "sky": "#A1CCE4",
    "navy": "#1F3C88",         # names of the subject
    "salmon": "#DA7756",       # the comparator
    "alert": "#C00000",        # growth rates, annotations
    "up": "#7A9A3A",
    "down": "#E0281E",
}
THEMES = {"teal": TEAL, "mono": MONO}

# Stacked-bar families: one hue per family, depth = recency / importance.
FAMILY_RAMPS = {
    "warm": ["#E9514E", "#BF7573", "#C28D8B", "#C9AEAB"],
    "cool": ["#0D4753", "#19889F", "#ABD0D9", "#DEF0F0"],
    "green": ["#1D6B55", "#288B6F", "#8CC5B2", "#D6ECE4"],
    "gold": ["#B98600", "#F4BA01", "#F8D873", "#FCEFC4"],
}
ACCENTS = ["#288B6F", "#F4BA01", "#000000", "#999999"]

_CJK = re.compile(r"[⺀-鿿豈-﫿＀-￯]")
_LATIN_FONTS = ["Roboto", "Inter", "Helvetica Neue", "Helvetica", "Arial", "Liberation Sans"]
_CJK_FONTS = ["Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans SC", "Source Han Sans CN",
              "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", "SimHei"]
_font_state = {"done": False, "cjk": False}


def setup_fonts():
    """Pick the best installed Latin + CJK fonts. Returns True when CJK text can render."""
    if _font_state["done"]:
        return _font_state["cjk"]
    have = {f.name for f in fm.fontManager.ttflist}
    latin = [f for f in _LATIN_FONTS if f in have][:1]
    cjk = [f for f in _CJK_FONTS if f in have]
    plt.rcParams["font.family"] = latin + cjk + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["svg.fonttype"] = "none"
    plt.rcParams["pdf.fonttype"] = 42
    _font_state.update(done=True, cjk=bool(cjk))
    return bool(cjk)


def _check_cjk(*texts):
    if not setup_fonts() and any(_CJK.search(str(t)) for t in texts if t):
        warnings.warn("Chinese text found but no CJK font is installed; install Noto Sans SC "
                      "or Source Han Sans, otherwise labels render as boxes.", stacklevel=3)


def _theme(theme):
    return THEMES[theme] if isinstance(theme, str) else theme


def ramp(base, n):
    """n shades of one hue, deep to pale."""
    r, g, b = to_rgb(base)
    out = []
    for i in range(n):
        t = 0 if n == 1 else i / (n - 1) * 0.82
        out.append((r + (1 - r) * t, g + (1 - g) * t, b + (1 - b) * t))
    return out


def fmt(kind):
    """Tick/label formatter from a short code: '$', '$k', '%', '%0', 'x', ',', or a format string."""
    if callable(kind):
        return kind
    table = {
        None: lambda v: f"{v:,.0f}" if abs(v - round(v)) < 1e-9 else f"{v:,.1f}",
        ",": lambda v: f"{v:,.0f}",
        "$": lambda v: f"${v:,.0f}",
        "$2": lambda v: f"${v:,.2f}",
        "%": lambda v: f"{v:.0f}%",
        "%1": lambda v: f"{v:.1f}%",
        "x": lambda v: f"{v:.1f}x",
    }
    if kind in table:
        return table[kind]
    return lambda v: kind.format(v)


def _tickfmt(kind):
    f = fmt(kind)
    return FuncFormatter(lambda v, _pos: f(v))


def _xpos(x, key):
    """Resolve an x reference: a label in x, or a (fractional) index."""
    if isinstance(key, (int, float)):
        return float(key)
    return float(list(x).index(key))


def _thin_xticks(ax, x, every=None, rotation=45, color="#606060", size=11):
    n = len(x)
    if every is None:
        every = max(1, int(np.ceil(n / 24)))
    idx = list(range(0, n, every))
    if every > 1 and idx[-1] != n - 1 and (n - 1 - idx[-1]) > every * 0.6:
        idx.append(n - 1)
    ax.set_xticks(idx)
    ax.set_xticklabels([x[i] for i in idx], rotation=rotation,
                       ha="right" if rotation else "center", rotation_mode="anchor",
                       color=color, fontsize=size)


def _save(fig, out, dpi=200):
    if out:
        fig.savefig(out, dpi=dpi, facecolor="white")
    return fig


# --------------------------------------------------------------------------
# Frames
# --------------------------------------------------------------------------
def _wrap(text, width):
    """Wrap to `width` Latin-character units (a CJK glyph counts as two). Manual \\n is kept.
    Lines are balanced so a title never ends on a one- or two-character orphan."""
    if not text:
        return []
    out = []
    for para in str(text).split("\n"):
        toks = re.findall(r"[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef]|[^\s\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef]+|\s+", para)
        wid = lambda t: sum(2 if _CJK.match(c) else 1 for c in t)  # noqa: E731
        total = sum(wid(t) for t in toks)
        n = max(1, int(np.ceil(total / width)))
        target = total / n + 1.5
        line, lw = "", 0
        for t in toks:
            if line and lw + wid(t.rstrip()) > min(width, target) and len(out) + 1 < 99:
                out.append(line.rstrip())
                line, lw = "", 0
                if not t.strip():
                    continue
            line += t
            lw += wid(t)
        out.append(line.rstrip())
    return out


def _wrap_soft(text, width):
    """Like _wrap, but split a two-line paragraph after a comma or stop when both halves fit."""
    wid = lambda t: sum(2 if _CJK.match(c) else 1 for c in t)  # noqa: E731
    out = []
    for para in str(text).split("\n"):
        if wid(para) <= width:
            out.append(para)
            continue
        best = None
        for m in re.finditer(r"[，、；：。,;:]", para):
            head, tail = para[:m.end()], para[m.end():].lstrip()
            if tail and wid(head) <= width and wid(tail) <= width:
                score = abs(wid(head) - wid(tail))
                if best is None or score < best[0]:
                    best = (score, head, tail)
        out += [best[1], best[2]] if best else _wrap(para, width)
    return out


def _frame_teal(figsize=(10, 7.2), title=None, brand=None, plot_rect=None, source=None, unit=None,
                top_pad=0.0):
    setup_fonts()
    T = TEAL
    fig = plt.figure(figsize=figsize, facecolor="white")
    wide = figsize[0] / 10
    tl = _wrap(title, int(46 * wide))
    top = 0.90 if not tl else (0.815 if len(tl) == 1 else 0.765)
    if unit:
        top -= 0.03
    top -= top_pad
    bottom = 0.30 if not source else 0.315
    rect = plot_rect or [0.125, bottom, 0.80, top - bottom]
    ax = fig.add_axes(rect)
    if tl:
        fig.text(0.075, 0.955, "\n".join(tl), fontsize=23 if len(tl) == 1 else 20,
                 fontweight="bold", color=T["ink"], ha="left", va="top", linespacing=1.18)
    if unit:
        fig.text(rect[0] - 0.05, top + 0.022 + top_pad, unit, fontsize=11, fontweight="bold",
                 color=T["label"], ha="left", va="bottom")
    if source:
        sl = _wrap(source, int(118 * wide))[:2]
        fig.text(0.075, 0.035, "\n".join(sl), fontsize=9.5, color="#808080", ha="left",
                 va="bottom", linespacing=1.3)
    if brand:
        fig.text(0.925, 0.075 if not source else 0.085, brand, fontsize=12, fontweight="bold",
                 color=T["ink"], ha="right", va="center")
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.grid(axis="y", color=T["grid"], linewidth=1.0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0, labelsize=11, colors=T["tick"])
    return fig, ax


def _legend_below(fig, ax, handles, labels, T, y=0.125, max_cols=6):
    n = len(labels)
    total = sum(len(str(s)) for s in labels) + 4 * n
    ncol = n if total < 92 else int(np.ceil(n / np.ceil(total / 92)))
    ncol = min(ncol, max_cols + 1)
    leg = fig.legend(handles, labels, loc="center", bbox_to_anchor=(0.5, y), ncol=ncol,
                     frameon=False, fontsize=11, handlelength=1.5, columnspacing=1.6,
                     handletextpad=0.8, labelcolor=T["legend"])
    return leg


def _frame_mono(figsize=(7.2, 4.9), title=None, source=None, unit=None, fig=None, cell=None,
                side=0.0):
    """Sell-side frame: bold conclusion title, hairline, plot, hairline, source.

    cell = (left, bottom, width, height) in figure fractions lets several frames share a figure.
    side = share of the width kept on the right for side notes (see _side_notes).
    Returns (fig, ax)."""
    setup_fonts()
    M = MONO
    if fig is None:
        fig = plt.figure(figsize=figsize, facecolor="white")
    L, B, W, H = cell or (0.04, 0.03, 0.92, 0.94)
    fh = fig.get_figheight()
    pt = 1 / 72 / fh                       # one point in figure-fraction units
    y = B + H
    title_h = 0.0
    if title:
        lines = _wrap(title, max(28, int(W * fig.get_figwidth() * 10.2)))
        t = fig.text(L, y, "\n".join(lines), fontsize=12.5, fontweight="bold", color=M["ink"],
                     ha="left", va="top", linespacing=1.2)
        title_h = (len(lines) * 12.5 * 1.25 + 9) * pt
        fig.add_artist(Line2D([L, L + W], [y - title_h, y - title_h], color=M["rule"],
                              linewidth=0.8, transform=fig.transFigure))
        del t
    src_h = 0.0
    if source:
        sl = _wrap(source, max(40, int(W * fig.get_figwidth() * 15.5)))[:3]
        src_h = (15 + 11.5 * len(sl)) * pt
        fig.add_artist(Line2D([L, L + W], [B + src_h, B + src_h], color=M["rule"],
                              linewidth=0.8, transform=fig.transFigure))
        fig.text(L, B + src_h - 7 * pt, "\n".join(sl), fontsize=8.5, color=M["ink"], ha="left",
                 va="top", linespacing=1.3)
    unit_h = 20 * pt if unit else 0
    if unit:
        fig.text(L + 0.02 * W, y - title_h - 8 * pt, unit, fontsize=10, fontweight="bold",
                 color=M["ink"], ha="left", va="top")
    pad_t, pad_b = 16 * pt, 34 * pt
    ax_w = W * 0.83 if not side else W * (1 - side) - W * 0.105
    ax = fig.add_axes([L + 0.085 * W, B + src_h + pad_b, ax_w,
                       H - title_h - src_h - unit_h - pad_t - pad_b])
    ax._ic_bounds = (B + src_h + 7 * pt, y - title_h - unit_h - 7 * pt)
    if side:
        ax._ic_side = (L + W * (1 - side) + 0.01 * W, L + W, y - title_h - 10 * pt, B + src_h + 10 * pt)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(M["ink"])
    ax.spines["bottom"].set_linewidth(1.2)
    ax.grid(axis="y", color=M["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0, labelsize=10, colors=M["tick"])
    return fig, ax


def _fit(ax, *twins):
    """Shrink the axes until tick labels and legends clear the title rule and the source line."""
    fig = ax.figure
    floor, ceil = ax._ic_bounds
    for _ in range(3):
        fig.canvas.draw()
        rend = fig.canvas.get_renderer()
        boxes = [a.get_tightbbox(rend) for a in (ax, *twins) if a is not None]
        inv = fig.transFigure.inverted()
        lo = min(inv.transform((0, b.y0))[1] for b in boxes)
        hi = max(inv.transform((0, b.y1))[1] for b in boxes)
        pos = ax.get_position()
        nb, nt = pos.y0 + max(0, floor - lo), pos.y1 - max(0, hi - ceil)
        if nb - pos.y0 < 1e-4 and pos.y1 - nt < 1e-4:
            break
        for a in (ax, *twins):
            if a is not None:
                a.set_position([pos.x0, nb, pos.width, max(0.05, nt - nb)])


def _numbered(title, number, lang=None):
    if number is None or not title:
        return title
    if lang == "zh" or (lang is None and _CJK.search(title)):
        return f"图 {number}：{title}"
    return f"Figure {number}: {title}"


# --------------------------------------------------------------------------
# Recipe 1 — trend lines with event dividers
# --------------------------------------------------------------------------
def _place_chips(fig, ax, events, x, T, chip="soft", at="top"):
    """Vertical dividers + rounded label chips, staggered so they never overlap."""
    ink = chip == "ink"
    line_c = T["ink"] if ink else T["event"]
    text_c = T["ink"] if ink else T["event"]
    trans = ax.get_xaxis_transform()
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    placed = []
    ax_h = ax.get_window_extent(rend).height
    step = 22 / ax_h * fig.dpi / 100          # one chip row in axes fraction
    for ev in sorted(events, key=lambda e: _xpos(x, e["at"])):
        xv = _xpos(x, ev["at"])
        ax.plot([xv, xv], [0, 1], transform=trans, color=line_c,
                linewidth=1.0 if ink else 1.3, zorder=2.5, solid_capstyle="butt")
        lines = str(ev["label"]).split("\n")
        level = 0
        while True:
            arts, boxes, clash = [], [], False
            for k, ln in enumerate(lines):
                row = level + k
                y = (0.955 - row * step) if at == "top" else (0.045 + (len(lines) - 1 - k + level) * step)
                t = ax.text(xv, y, ln, transform=trans, ha="center", va="center", fontsize=9.5,
                            fontweight="bold", color=text_c, zorder=6,
                            bbox=dict(boxstyle="round,pad=0.28,rounding_size=0.35", fc="white",
                                      ec=T["chip_edge"], lw=0.9))
                bb = t.get_window_extent(rend).expanded(1.04, 1.25)
                arts.append(t)
                boxes.append(bb)
                if any(bb.overlaps(p) for p in placed):
                    clash = True
            if not clash or level > 7:
                placed.extend(boxes)
                break
            for t in arts:
                t.remove()
            level += 1


def trend_events(x, series, events=None, title=None, ylabel=None, yfmt=None, ylim=None,
                 chip="soft", chip_at="top", colors=None, linewidth=2.4, xtick_every=None,
                 source=None, unit=None, brand=None, eras=None, marks=None, out=None,
                 figsize=(10, 7.2)):
    """Multi-line trend with vertical event dividers (model launches, policy dates, price moves).

    x: list of category labels (dates as strings). series: {name: values}.
    events: [{"at": label-or-index, "label": "Opus 4.5\\nClaude Cowork"}].
    chip: "soft" grey chips for context events, "ink" dark chips when the events ARE the story.
    eras: [{"from": x, "label": "…"}, …] named stretches in a strip above the plot.
    marks: dashed boxes, red crosses, pins and numbered dots (see _draw_marks)."""
    T = TEAL
    _check_cjk(title, ylabel, source, unit, *series, *[e["label"] for e in eras or []])
    fig, ax = _frame_teal(figsize, title, brand, source=source, unit=unit,
                          top_pad=0.05 if eras else 0.0)
    xs = np.arange(len(x))
    cols = colors or T["series"]
    handles = []
    for i, (name, vals) in enumerate(series.items()):
        v = np.array([np.nan if a is None else a for a in vals], dtype=float)
        (ln,) = ax.plot(xs[:len(v)], v, color=cols[i % len(cols)], linewidth=linewidth,
                        solid_joinstyle="round", zorder=3 + (0.5 if i == 0 else 0))
        handles.append(ln)
    side = 0 if len(x) > 14 else 0.3          # short series get breathing room at both ends
    ax.set_xlim(-side, len(x) - 1 + side)
    if ylim:
        ax.set_ylim(*ylim)
    else:
        ax.set_ylim(bottom=min(0, ax.get_ylim()[0]))
    ax.yaxis.set_major_locator(MaxNLocator(10))
    ax.yaxis.set_major_formatter(_tickfmt(yfmt))
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=11, fontweight="bold", color=T["label"], labelpad=10)
    _thin_xticks(ax, x, xtick_every, color=T["tick"])
    ax.axhline(ax.get_ylim()[0], color="#D5D5D5", linewidth=1.2, zorder=2)
    if events:
        _place_chips(fig, ax, events, list(x), T, chip, chip_at)
    if eras:
        _draw_eras(ax, x, eras, color=T["ink"])
    _draw_marks(ax, x, marks, dict(series), T)
    _legend_below(fig, ax, handles, list(series), T)
    return _save(fig, out)


# --------------------------------------------------------------------------
# Recipe 2 — stacked bars coloured by family
# --------------------------------------------------------------------------
def family_colors(families, minor=None):
    """{family: [members newest→oldest]} → {member: colour}. Families take warm / cool / green /
    gold ramps in order; `minor` members take the accent colours."""
    out = {}
    ramps = list(FAMILY_RAMPS.values())
    for i, (_fam, members) in enumerate(families.items()):
        base = ramps[i % len(ramps)]
        shades = base if len(members) <= len(base) else ramp(base[0], len(members))
        for m, c in zip(members, shades):
            out[m] = c
    for j, m in enumerate(minor or []):
        out[m] = ACCENTS[j % len(ACCENTS)]
    return out


def stacked_family(x, layers, families=None, minor=None, colors=None, title=None, ylabel=None,
                   yfmt=None, percent=False, xtick_every=None, source=None, unit=None,
                   brand=None, totals=False, marks=None, out=None, figsize=(10, 7.2)):
    """Stacked bars where colour encodes family first, generation second.

    layers: {member: values} in bottom-to-top order.
    families: {"Sonnet": ["Sonnet 5.5", "Sonnet 5", ...], "Opus": [...]} newest first.
    minor: small leftovers that get accent colours and sit on top.
    totals: write each bar's total above it.  marks: see _draw_marks (a red cross over a
    forecast, a dashed box around the years that matter)."""
    T = TEAL
    _check_cjk(title, ylabel, source, unit, *layers)
    fig, ax = _frame_teal(figsize, title, brand, source=source, unit=unit)
    cmap = dict(family_colors(families or {}, minor))
    cmap.update(colors or {})
    spare = iter(T["series"])
    xs = np.arange(len(x))
    data = {k: np.nan_to_num(np.array(v, dtype=float)) for k, v in layers.items()}
    if percent:
        tot = sum(data.values())
        data = {k: np.divide(v, tot, out=np.zeros_like(v), where=tot > 0) * 100 for k, v in data.items()}
    bottom = np.zeros(len(x))
    handles = []
    for name, v in data.items():
        c = cmap.get(name) or next(spare)
        ax.bar(xs, v, bottom=bottom, width=0.74, color=c, edgecolor="white", linewidth=0.35, zorder=3)
        bottom += v
        handles.append(Patch(facecolor=c, edgecolor="#00000022", linewidth=0.5))
    ax.set_xlim(-0.7, len(x) - 0.3)
    if percent:
        ax.set_ylim(0, 100)
    elif totals:
        ax.set_ylim(0, bottom.max() * 1.1)
        tf = fmt(yfmt)
        for i, v in enumerate(bottom):
            ax.annotate(tf(v), (i, v), xytext=(0, 4), textcoords="offset points", ha="center",
                        va="bottom", fontsize=9.5, fontweight="bold", color=T["ink"], zorder=6)
    _draw_marks(ax, x, marks, {"total": bottom}, T)
    ax.yaxis.set_major_locator(MaxNLocator(10))
    ax.yaxis.set_major_formatter(_tickfmt("%" if percent and yfmt is None else yfmt))
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=11, fontweight="bold", color=T["label"], labelpad=10)
    _thin_xticks(ax, x, xtick_every, color=T["tick"])
    order = list(layers)
    if families:                      # legend reads family by family, newest first
        ordered = [m for mem in families.values() for m in mem if m in layers]
        ordered += [m for m in order if m not in ordered]
        handles = [handles[order.index(m)] for m in ordered]
        order = ordered
    leg = _legend_below(fig, ax, handles, order, T, y=0.135)
    for h in leg.legend_handles:
        h.set_height(11)
        h.set_width(11)
    return _save(fig, out)


# --------------------------------------------------------------------------
# Recipe 3 — bars + line on two axes (also the building block of panel grids)
# --------------------------------------------------------------------------
def _draw_bar_line(ax, x, bars, line=None, theme="mono", bar_fmt=None, line_fmt=None,
                   left_fmt=None, right_fmt=None, bar_name=None, line_name=None,
                   highlight=None, forecast_from=None, labels=True, right_ylim=None,
                   left_ylim=None, legend="top", note=None, marks=None):
    T = _theme(theme)
    mono = T["name"] == "mono"
    xs = np.arange(len(x))
    b = np.array(bars, dtype=float)
    base_c = T["greys"][0] if mono else T["bar"]
    cols = [base_c] * len(x)
    if forecast_from is not None:
        f0 = int(_xpos(x, forecast_from))
        for i in range(f0, len(x)):
            cols[i] = "#DEDEDE" if mono else T["bar_soft"]
    for h in ([highlight] if isinstance(highlight, (str, int)) else (highlight or [])):
        cols[int(_xpos(x, h))] = T["highlight"] if mono else T["ink"]
    ax.bar(xs, b, width=0.56 if mono else 0.72, color=cols, zorder=3,
           edgecolor="none" if mono else T["bar_edge"], linewidth=0.6)
    ax.set_xticks(xs)
    ax.set_xticklabels(x, fontsize=10 if mono else 11, color=T["tick"])
    ax.set_xlim(-0.6, len(x) - 0.4)
    top = np.nanmax(b) if len(b) else 1
    ax.set_ylim(*(left_ylim or (min(0, np.nanmin(b)), top * 1.16)))
    ax.yaxis.set_major_formatter(_tickfmt(left_fmt))
    ax.yaxis.set_major_locator(MaxNLocator(9, steps=[1, 2, 5, 10]))
    bf, lf = fmt(bar_fmt), fmt(line_fmt)
    bar_labels, line_labels = [], []
    if labels:
        for i, v in enumerate(b):
            bar_labels.append(ax.annotate(bf(v), (i, v), xytext=(0, 5), textcoords="offset points",
                                          ha="center", va="bottom", fontsize=10, color=T["tick"],
                                          zorder=6))
    handles = [Patch(facecolor=base_c)]
    names = [bar_name]
    ax2 = None
    if line is not None:
        ax2 = ax.twinx()
        for s in ax2.spines.values():
            s.set_visible(False)
        lv = np.array([np.nan if a is None else a for a in line], dtype=float)
        lc = T["line"] if mono else T["ink"]
        ax2.plot(xs, lv, color=lc, linewidth=2.6 if mono else 2.2, marker="D" if mono else None,
                 markersize=5.5, zorder=5)
        lo, hi = np.nanmin(lv), np.nanmax(lv)
        ax2.yaxis.set_major_formatter(_tickfmt(right_fmt or line_fmt))
        ax2.yaxis.set_major_locator(MaxNLocator(9, steps=[1, 2, 5, 10]))
        l0, l1 = ax.get_ylim()
        lt_ticks = [t for t in ax.get_yticks() if l0 - 1e-9 <= t <= l1 + 1e-9]
        if right_ylim:
            ax2.set_ylim(*right_ylim)
        elif l0 == 0 and lo >= 0 and len(lt_ticks) > 1:
            # share the left gridlines: pick the smallest round step that fits the line
            step_l = lt_ticks[1] - lt_ticks[0]
            need = hi * 1.12 / (l1 / step_l)
            mag = 10 ** np.floor(np.log10(need))
            step_r = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= need - 1e-12)
            ax2.set_ylim(0, l1 / step_l * step_r)
            ax2.set_yticks([k * step_r for k in range(len(lt_ticks))])
        else:
            ax2.set_ylim(min(0, lo), hi * 1.22)
        ax2.tick_params(axis="y", length=0, labelsize=10 if mono else 11, colors=T["tick"])
        ax2.grid(False)
        if labels:
            for i, v in enumerate(lv):
                if np.isnan(v):
                    continue
                line_labels.append((i, ax2.annotate(
                    lf(v), (i, v), xytext=(0, 7), textcoords="offset points", ha="center",
                    va="bottom", fontsize=10, fontweight="bold", color=T["ink"], zorder=7)))
            _declash(ax, ax2, bar_labels, line_labels, b, lv)
        handles.append(Line2D([0], [0], color=lc, linewidth=2.4, marker="D" if mono else None,
                              markersize=5))
        names.append(line_name)
    if note:
        ax.text(0.30, 0.86, note, transform=ax.transAxes, fontsize=10, color=T.get("alert", "#C00000"),
                ha="left", va="top", linespacing=1.35)
    _draw_marks(ax, list(x), marks, {"bars": b}, T)
    if legend and any(names):
        hs = [h for h, n in zip(handles, names) if n]
        ns = [n for n in names if n]
        if legend == "top":
            ax.legend(hs, ns, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=len(ns),
                      frameon=False, fontsize=10, handlelength=1.9, columnspacing=1.6,
                      labelcolor=T["legend"])
        else:
            ax.legend(hs, ns, loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=len(ns),
                      frameon=False, fontsize=10, handlelength=1.9, columnspacing=1.6,
                      labelcolor=T["legend"])
    return ax2


def _declash(ax, ax2, bar_labels, line_labels, bars, line_vals):
    """Bar values always sit on top of their bars. Where the line passes through that spot,
    the line's value drops below its marker, or the bar's value steps up above both."""
    fig = ax.figure
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    px = fig.dpi / 72
    for i, lt in line_labels:
        bt = bar_labels[i]
        bb, lb = bt.get_window_extent(rend), lt.get_window_extent(rend)
        mk = ax2.transData.transform((i, line_vals[i]))[1]          # marker height in pixels
        on_marker = bb.y0 - 5 * px < mk < bb.y1 + 5 * px
        if on_marker:                                   # marker sits where the bar's value is
            top = ax.transData.transform((0, bars[i]))[1]
            bt.set_position((0, (lb.y1 - top) / px + 3))
        elif bb.expanded(1.05, 1.15).overlaps(lb):      # only the two numbers collide
            lt.set_position((0, -8))
            lt.set_va("top")


def bar_line(x, bars, line=None, title=None, source=None, unit=None, number=None, theme="mono",
             ylabel=None, right_label=None, notes=None, notes_title=None, out=None, figsize=None,
             brand=None, **kw):
    """Level as bars, ratio as a line. theme="mono" → grey bars, labelled; "teal" → pale bars.
    notes (mono only): numbered conclusions in a column on the right."""
    _check_cjk(title, source, unit)
    if _theme(theme)["name"] == "mono":
        size, side = _prep_notes(notes, figsize or (7.2, 4.9))
        fig, ax = _frame_mono(size, _numbered(title, number), source, unit, side=side)
        _fit(ax, _draw_bar_line(ax, x, bars, line, "mono", **kw))
        if notes:
            _side_notes(fig, ax, notes, notes_title)
    else:
        T = TEAL
        fig, ax = _frame_teal(figsize or (10, 7.2), title, brand, source=source, unit=unit)
        kw.setdefault("labels", False)
        kw["legend"] = None
        ax2 = _draw_bar_line(ax, x, bars, line, "teal", **kw)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
        if ylabel:
            ax.set_ylabel(ylabel, fontsize=11, fontweight="bold", color=T["label"], labelpad=10)
        if ax2 is not None and right_label:
            ax2.set_ylabel(right_label, fontsize=11, fontweight="bold", color=T["label"],
                           rotation=270, labelpad=22)
        hs = [Line2D([0], [0], color=T["ink"], linewidth=2.2),
              Patch(facecolor=T["bar"], edgecolor=T["bar_edge"])]
        ns = [kw.get("line_name"), kw.get("bar_name")]
        pairs = [(h, n) for h, n in zip(hs, ns) if n]
        if pairs:
            _legend_below(fig, ax, [p[0] for p in pairs], [p[1] for p in pairs], T)
    return _save(fig, out)


def _draw_cost_steps(ax, groups, parts, colors=None, highlight=None, theme="mono"):
    """Share-of-total staircase: each part is a block that starts where the previous ended,
    one staircase per group, groups split by a dashed divider."""
    M = MONO
    cols = colors or [M["sky"], M["greys"][1], M["line"], M["greys"][3]]
    n = len(parts)
    width = 1.0
    gap = 0.9
    centers = []
    for g, (gname, vals) in enumerate(groups.items()):
        x0 = g * (n * width + gap)
        cum = 0.0
        for k, v in enumerate(vals):
            c = cols[k % len(cols)]
            ax.bar(x0 + k * width, v, bottom=cum, width=width, color=c, zorder=3, align="edge")
            strong = highlight is not None and gname == highlight and k == 0
            dark = k >= 2
            tiny = v < 5
            ax.text(x0 + (k + 0.5) * width, cum + v + 1.5 if tiny else cum + v / 2, f"{v:.0f}%",
                    ha="center", va="bottom" if tiny else "center", fontsize=10,
                    fontweight="bold" if strong else "normal",
                    color="white" if dark and not tiny else M["ink"], zorder=6)
            cum += v
        centers.append(x0 + n * width / 2)
        if g:
            ax.axvline(x0 - gap / 2, color=M["ink"], linewidth=0.9, linestyle=(0, (5, 4)), zorder=4,
                       ymin=-0.12, clip_on=False)
    ax.set_xticks(centers)
    ax.set_xticklabels(list(groups), fontsize=10)
    ax.set_xlim(-gap / 2, len(groups) * (n * width + gap) - gap / 2)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_locator(MaxNLocator(10))
    ax.yaxis.set_major_formatter(_tickfmt("%"))
    ax.legend([Patch(facecolor=cols[k % len(cols)]) for k in range(n)], parts, loc="lower center",
              bbox_to_anchor=(0.5, 1.0), ncol=n, frameon=False, fontsize=10, handlelength=0.8,
              handleheight=0.8, columnspacing=1.8)


def _draw_bars(ax, x, values, highlight=None, value_fmt=None, forecast_from=None, note=None,
               left_fmt=None, hide_y=False, marks=None):
    M = MONO
    if left_fmt is None and value_fmt in ("%", "%1", "$", "$2"):
        left_fmt = value_fmt[0]              # the axis speaks the same unit as the labels
    _draw_bar_line(ax, x, values, None, "mono", bar_fmt=value_fmt, left_fmt=left_fmt,
                   highlight=highlight, forecast_from=forecast_from, legend=None, note=note,
                   marks=marks)
    if hide_y:
        ax.set_yticklabels([])
    if len(x) > 6 or max(len(str(s)) for s in x) > 9:
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    del M


# --------------------------------------------------------------------------
# Recipe 4 — panel grid ("four in one")
# --------------------------------------------------------------------------
_PANEL_DRAWERS = {}


def panel_grid(panels, ncols=2, start_number=1, out=None, figsize=None, lang=None):
    """Several small conclusions on one canvas. Each panel is a dict:

    {"kind": "bar_line" | "cost_steps" | "bars" | "area" | "lines" | "waterfall" | "aligned"
             | "donut" | "stacked_total",
     "title": "conclusion sentence", "source": "...", "unit": "Unit: RMB m", ...recipe args}

    Titles are numbered automatically from start_number (pass start_number=None to skip)."""
    setup_fonts()
    n = len(panels)
    nrows = int(np.ceil(n / ncols))
    figsize = figsize or (7.6 * ncols, 5.3 * nrows)
    fig = plt.figure(figsize=figsize, facecolor="white")
    gx, gy = 0.045, 0.05
    cw = (1 - 0.06 - gx * (ncols - 1)) / ncols
    ch = (1 - 0.05 - gy * (nrows - 1)) / nrows
    for i, p in enumerate(panels):
        p = dict(p)
        r, c = divmod(i, ncols)
        cell = (0.03 + c * (cw + gx), 1 - 0.025 - (r + 1) * ch - r * gy, cw, ch)
        kind = p.pop("kind")
        title = p.pop("title", None)
        num = None if start_number is None else start_number + i
        _check_cjk(title, p.get("source"), p.get("unit"))
        _, ax = _frame_mono(title=_numbered(title, num, lang), source=p.pop("source", None),
                            unit=p.pop("unit", None), fig=fig, cell=cell)
        twin = _PANEL_DRAWERS[kind](ax, **p)
        _fit(ax, twin)
    return _save(fig, out)


# --------------------------------------------------------------------------
# Recipe 5 — stacked area with one highlighted layer
# --------------------------------------------------------------------------
def _draw_area(ax, x, layers, highlight=None, annotation=None, yfmt=None, xtick_every=None,
               theme="mono", marks=None):
    M = MONO
    xs = np.arange(len(x))
    names = list(layers)
    highlight = highlight or names[0]
    greys = iter(["#B0B0B0", "#808080", "#595959", "#404040", "#D0D0D0"])
    cols = [M["highlight"] if nme == highlight else next(greys) for nme in names]
    ys = [np.nan_to_num(np.array(layers[nme], dtype=float)) for nme in names]
    ax.stackplot(xs, *ys, colors=cols, zorder=3, linewidth=0)
    ax.plot(xs, np.sum(ys, axis=0), color="#808080", linewidth=1.0, zorder=4)
    ax.set_xlim(0, len(x) - 1)
    ax.set_ylim(0, np.sum(ys, axis=0).max() * 1.14)
    ax.yaxis.set_major_locator(MaxNLocator(7))
    ax.yaxis.set_major_formatter(_tickfmt(yfmt))
    ax.tick_params(axis="y", labelsize=11.5, colors=M["tick_soft"])
    _thin_xticks(ax, x, xtick_every, color=M["tick"], size=10)
    ax.tick_params(axis="x", length=4, width=1.1, color=M["ink"])
    ax.legend([Patch(facecolor=c) for c in cols], names, loc="upper center",
              bbox_to_anchor=(0.5, 1.0), ncol=len(names), frameon=False, fontsize=10.5,
              handlelength=0.8, handleheight=0.8, columnspacing=1.5, borderaxespad=0.2)
    if annotation:
        xv = _xpos(list(x), annotation["at"])
        y_to = annotation.get("y", 0)
        top = ax.get_ylim()[1]
        y_from = annotation.get("text_y", top * 0.50)
        ax.annotate("", xy=(xv, y_to), xytext=(xv, y_from), zorder=8,
                    arrowprops=dict(arrowstyle="-|>", color=M["alert"], linewidth=0.9,
                                    linestyle=(0, (3, 2)), mutation_scale=16))
        ha = annotation.get("ha", "left" if xv < len(x) * 0.25 else "center")
        ax.text(xv - (0.0 if ha != "left" else 0.0), y_from + top * 0.01, annotation["text"],
                color=M["alert"], fontsize=11, ha="center" if ha == "center" else ha, va="bottom",
                linespacing=1.12, zorder=9,
                path_effects=[pe.withStroke(linewidth=2.6, foreground="white", alpha=0.85)])
    _draw_marks(ax, x, marks, {"total": np.sum(ys, axis=0)})


def area_highlight(x, layers, highlight=None, annotation=None, title=None, source=None, unit=None,
                   number=None, yfmt=None, xtick_every=None, marks=None, notes=None, notes_title=None,
                   out=None, figsize=(7.4, 5.0)):
    """Stacked area: the layer that carries the story is tinted, the rest step down in grey.

    annotation: {"at": x-label-or-index, "text": "Announced 30%\\nprice hike", "y": 0}"""
    _check_cjk(title, source, unit, *layers)
    figsize, side = _prep_notes(notes, figsize)
    fig, ax = _frame_mono(figsize, _numbered(title, number), source, unit, side=side)
    _draw_area(ax, x, layers, highlight, annotation, yfmt, xtick_every, marks=marks)
    _fit(ax)
    if notes:
        _side_notes(fig, ax, notes, notes_title)
    return _save(fig, out)


def _draw_lines(ax, x, series, yfmt=None, colors=None, end_labels=True, xtick_every=None,
                steps=False, ylim=None, marks=None):
    """Subject vs comparator lines: navy for the subject, salmon for the comparator, grey after."""
    M = MONO
    xs = np.arange(len(x))
    cols = colors or [M["navy"], M["salmon"], M["line"], M["greys"][1]]
    for i, (name, vals) in enumerate(series.items()):
        v = np.array([np.nan if a is None else a for a in vals], dtype=float)
        ax.plot(xs, v, color=cols[i % len(cols)], linewidth=1.9, zorder=4,
                drawstyle="steps-post" if steps else "default")
        ok = np.where(~np.isnan(v))[0]
        if end_labels and len(ok):
            ax.annotate(name, (ok[-1], v[ok[-1]]), xytext=(5, 0), textcoords="offset points",
                        fontsize=9.5, fontweight="bold", color=cols[i % len(cols)], va="center",
                        annotation_clip=False)
    side = 0 if len(x) > 14 else 0.4
    ax.set_xlim(-side, len(x) - 1 + side)
    if ylim:
        ax.set_ylim(*ylim)
    ax.yaxis.set_major_formatter(_tickfmt(yfmt))
    long = len(x) > 8 or max(len(str(v)) for v in x) > 9
    _thin_xticks(ax, x, xtick_every, rotation=45 if long else 0, color=M["tick"], size=10)
    if not end_labels:
        ax.legend([Line2D([0], [0], color=cols[i % len(cols)], linewidth=2) for i in range(len(series))],
                  list(series), loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=len(series),
                  frameon=False, fontsize=10)
    _draw_marks(ax, x, marks, dict(series))


_PANEL_DRAWERS.update(bar_line=_draw_bar_line, cost_steps=_draw_cost_steps, bars=_draw_bars,
                      area=_draw_area, lines=_draw_lines)


# --------------------------------------------------------------------------
# Recipe 6 — scenario fan + value-driver table
# --------------------------------------------------------------------------
def scenario_fan(history, now, base, upside, downside, name=None, now_label=None,
                 horizon_label="+12 mo.", table=None, table_title=None, source=None,
                 price_fmt=None, out=None, figsize=(9.2, 5.0), labels=None):
    """Past path on the left, three futures on the right, the numbers behind them underneath.

    history: past values (oldest → newest). now: current value. base/upside/downside: targets.
    table: {"columns": ["Total rev", ...],
            "rows": {"upside": [...], "base": [...], "downside": [...]},
            "row_labels": {"upside": "HK$1,384 upside", ...}}"""
    setup_fonts()
    M = MONO
    L = {"upside": "Upside", "base": "Base", "downside": "Downside",
         "ratio": "Upside to Downside"}
    L.update(labels or {})
    _check_cjk(name, now_label, horizon_label, source, table_title, *L.values())
    has_table = bool(table)
    fig = plt.figure(figsize=figsize, facecolor="white")
    a_bot, a_top = (0.50, 0.83) if has_table else (0.20, 0.80)
    ax = fig.add_axes([0.185, a_bot, 0.50, a_top - a_bot])
    h = np.array(history, dtype=float)
    n = len(h)
    end = (n - 1) * 4.7                     # history takes ~21% of the width
    green = LinearSegmentedColormap.from_list("up", ["#F1F5E6", "#B5CB8B", "#6B962C"])
    red = LinearSegmentedColormap.from_list("dn", ["#F3C9C4", "#CC7A6C", "#A3321F"])
    grad = np.linspace(0, 1, 256).reshape(1, -1)
    ax.imshow(grad, extent=(n - 1, end, now, upside), cmap=green, aspect="auto", zorder=2)
    ax.imshow(grad, extent=(n - 1, end, downside, now), cmap=red, aspect="auto", zorder=2)
    ax.plot([n - 1, end], [now, now], color="white", linewidth=2.2, zorder=3)
    ax.plot(np.arange(n), h, color="#808080", linewidth=1.5, zorder=4)
    ax.plot([n - 1, end], [now, base], color=M["ink"], linewidth=0.9, linestyle=(0, (1, 1.6)), zorder=5)
    ax.plot([n - 1, end], [now, base], "o", color=M["ink"], markersize=4, zorder=6, clip_on=False)
    ax.axvline(n - 1, color="#BDBDBD", linewidth=0.9, zorder=1)
    lo = min(h.min(), downside)
    hi = max(h.max(), upside)
    pad = (hi - lo) * 0.14
    ax.set_xlim(0, end * 1.085)
    ax.set_ylim(lo - pad * 1.2, hi + pad)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#C8C8C8")
    ax.set_xticks([])
    ax.yaxis.set_major_locator(MaxNLocator(6))
    ax.yaxis.set_major_formatter(_tickfmt(price_fmt or ","))
    ax.tick_params(axis="y", length=0, labelsize=10, colors="#808080", pad=10)
    for lab in ax.get_yticklabels():
        lab.set_fontweight("bold")
    pf = fmt(price_fmt or "{:,.1f}")
    blend = blended_transform_factory(fig.transFigure, ax.transData)
    pct = lambda v: f"{(v / now - 1) * 100:+.0f}%"  # noqa: E731
    for val, col, key in ((upside, "#6B8E23", "upside"), (base, M["ink"], "base"),
                          (downside, "#B22222", "downside")):
        ax.text(0.705, val, pf(val), transform=blend, fontsize=10.5, fontweight="bold", color=col,
                va="center", ha="left")
        ax.text(0.795, val, f"{L[key]}:", transform=blend, fontsize=10.5, fontweight="bold",
                color=col, va="center", ha="left")
        ax.text(0.955, val, pct(val), transform=blend, fontsize=10.5, fontweight="bold",
                color=col, va="center", ha="right")
    ratio = (upside - now) / max(now - downside, 1e-9)
    fig.text(0.875, a_top + 0.02, f"{L['ratio']}\n{ratio:.1f} to 1", fontsize=10.5,
             fontweight="bold", color="#808080", ha="center", va="bottom", linespacing=1.15)
    if name:
        fig.text(0.045, 0.975, name, fontsize=11, fontweight="bold", color=M["ink"],
                 ha="left", va="top")
    if now_label:
        ax.text(n - 1, 1.015, now_label, transform=ax.get_xaxis_transform(), fontsize=10.5,
                fontweight="bold", color=M["ink"], ha="center", va="bottom", linespacing=1.1)
    ax.text(end, -0.06, horizon_label, transform=ax.get_xaxis_transform(), fontsize=10.5,
            fontweight="bold", color=M["ink"], ha="center", va="top")
    if has_table:
        tx = fig.add_axes([0.045, 0.095, 0.91, 0.31])
        tx.axis("off")
        cols = table["columns"]
        rl = table.get("row_labels", {})
        xs = np.linspace(0.335, 1.0, len(cols))
        tx.text(0.0, 0.84, table_title or "", fontsize=12.5, fontweight="bold", color=M["ink"],
                ha="left", va="center", linespacing=1.25)
        for xc, cname in zip(xs, cols):
            tx.text(xc, 0.84, cname, fontsize=12, color=M["ink"], ha="right", va="center",
                    linespacing=1.25)
        for r, (key, col) in enumerate((("upside", M["up"]), ("base", M["ink"]), ("downside", M["down"]))):
            if key not in table["rows"]:
                continue
            y = 0.44 - r * 0.155
            tx.text(0.005, y, rl.get(key, L[key]), fontsize=12, color=col, ha="left", va="center")
            for xc, cell in zip(xs, table["rows"][key]):
                tx.text(xc, y, str(cell), fontsize=12, color=col, ha="right", va="center")
    if source:
        fig.text(0.045, 0.045, source, fontsize=11, color=M["ink"], ha="left", va="center")
    return _save(fig, out)


# --------------------------------------------------------------------------
# Recipe 7 — capability ladder (stage icons + dotted trajectory + annotated milestones)
# --------------------------------------------------------------------------
def _ico_chat(a, k):
    a.add_patch(FancyBboxPatch((0.08, 0.42), 0.50, 0.36, boxstyle="round,pad=0.02,rounding_size=0.06", **k))
    a.add_line(Line2D([0.18, 0.16, 0.30], [0.40, 0.26, 0.40], **_ln(k)))
    a.add_patch(FancyBboxPatch((0.44, 0.20), 0.46, 0.34, boxstyle="round,pad=0.02,rounding_size=0.06",
                               **{**k, "facecolor": "white"}))
    a.add_line(Line2D([0.74, 0.86, 0.80], [0.18, 0.06, 0.18], **_ln(k)))


def _ico_list(a, k):
    for y, segs in ((0.72, [(0.10, 0.30), (0.42, 0.90)]), (0.50, [(0.10, 0.22), (0.34, 0.62), (0.72, 0.90)]),
                    (0.28, [(0.10, 0.44), (0.56, 0.90)])):
        for x0, x1 in segs:
            a.add_line(Line2D([x0, x1], [y, y], **_ln(k)))


def _ico_coder(a, k):
    a.add_patch(Circle((0.5, 0.74), 0.15, **k))
    a.add_line(Line2D([0.20, 0.24, 0.36, 0.64, 0.76, 0.80], [0.30, 0.48, 0.56, 0.56, 0.48, 0.30], **_ln(k)))
    a.add_patch(FancyBboxPatch((0.24, 0.08), 0.52, 0.26, boxstyle="round,pad=0.01,rounding_size=0.03",
                               **{**k, "facecolor": "white"}))
    a.text(0.5, 0.21, "</>", fontsize=6.2, ha="center", va="center", color=k["edgecolor"], fontweight="bold")


def _ico_network(a, k):
    ang = np.deg2rad([90, 210, 330])
    outer = [(0.5 + 0.36 * np.cos(t), 0.47 + 0.36 * np.sin(t)) for t in ang]
    for i, p in enumerate(outer):
        q = outer[(i + 1) % 3]
        a.add_line(Line2D([p[0], q[0]], [p[1], q[1]], **_ln(k)))
        a.add_line(Line2D([p[0], 0.5], [p[1], 0.47], **_ln(k)))
    for p in outer + [(0.5, 0.47)]:
        a.add_patch(Circle(p, 0.10, **{**k, "facecolor": "white", "zorder": 3}))


def _ico_timer(a, k):
    a.add_patch(Circle((0.5, 0.44), 0.34, **k))
    a.add_line(Line2D([0.5, 0.5], [0.78, 0.92], **_ln(k)))
    a.add_line(Line2D([0.38, 0.62], [0.93, 0.93], **_ln(k)))
    a.add_line(Line2D([0.5, 0.5, 0.66], [0.62, 0.44, 0.52], **_ln(k)))
    a.add_patch(Circle((0.5, 0.44), 0.035, facecolor=k["edgecolor"], edgecolor="none"))


def _ico_screen(a, k):
    a.add_patch(FancyBboxPatch((0.08, 0.30), 0.84, 0.56, boxstyle="round,pad=0.01,rounding_size=0.04", **k))
    a.add_line(Line2D([0.5, 0.5], [0.30, 0.14], **_ln(k)))
    a.add_line(Line2D([0.28, 0.72], [0.12, 0.12], **_ln(k)))
    a.add_patch(Circle((0.40, 0.58), 0.11, **k))
    a.add_line(Line2D([0.60, 0.80], [0.66, 0.66], **_ln(k)))
    a.add_line(Line2D([0.60, 0.74], [0.52, 0.52], **_ln(k)))


def _ico_gear(a, k):
    for t in np.linspace(0, 2 * np.pi, 9)[:-1]:
        a.add_line(Line2D([0.5 + 0.28 * np.cos(t), 0.5 + 0.42 * np.cos(t)],
                          [0.5 + 0.28 * np.sin(t), 0.5 + 0.42 * np.sin(t)], **{**_ln(k), "linewidth": 2.6}))
    a.add_patch(Circle((0.5, 0.5), 0.29, **{**k, "facecolor": "white"}))
    a.add_patch(Circle((0.5, 0.5), 0.11, **k))


def _ico_doc(a, k):
    a.add_patch(Polygon([(0.20, 0.08), (0.20, 0.92), (0.62, 0.92), (0.80, 0.74), (0.80, 0.08)], closed=True, **k))
    a.add_line(Line2D([0.62, 0.62, 0.80], [0.92, 0.74, 0.74], **_ln(k)))
    for y in (0.56, 0.42, 0.28):
        a.add_line(Line2D([0.32, 0.68], [y, y], **_ln(k)))


def _ico_bars(a, k):
    for x, h in ((0.14, 0.30), (0.40, 0.52), (0.66, 0.78)):
        a.add_patch(Rectangle((x, 0.10), 0.20, h, **k))
    a.add_line(Line2D([0.06, 0.94], [0.10, 0.10], **_ln(k)))


def _ico_db(a, k):
    from matplotlib.patches import Ellipse
    a.add_line(Line2D([0.18, 0.18], [0.20, 0.78], **_ln(k)))
    a.add_line(Line2D([0.82, 0.82], [0.20, 0.78], **_ln(k)))
    for y in (0.78, 0.50, 0.20):
        a.add_patch(Ellipse((0.5, y), 0.64, 0.20, **{**k, "facecolor": "white" if y == 0.78 else "none"}))


def _ico_rocket(a, k):
    a.add_patch(Polygon([(0.5, 0.95), (0.68, 0.62), (0.68, 0.30), (0.32, 0.30), (0.32, 0.62)], closed=True, **k))
    a.add_patch(Circle((0.5, 0.58), 0.07, **k))
    a.add_line(Line2D([0.32, 0.16, 0.32], [0.48, 0.24, 0.30], **_ln(k)))
    a.add_line(Line2D([0.68, 0.84, 0.68], [0.48, 0.24, 0.30], **_ln(k)))
    a.add_line(Line2D([0.42, 0.5, 0.58], [0.22, 0.06, 0.22], **_ln(k)))


def _ico_target(a, k):
    for r in (0.40, 0.26, 0.11):
        a.add_patch(Circle((0.5, 0.5), r, **k))


def _ln(k):
    return dict(color=k["edgecolor"], linewidth=k["linewidth"], solid_capstyle="round")


ICONS = {"chat": _ico_chat, "list": _ico_list, "coder": _ico_coder, "network": _ico_network,
         "timer": _ico_timer, "screen": _ico_screen, "gear": _ico_gear, "doc": _ico_doc,
         "bars": _ico_bars, "db": _ico_db, "rocket": _ico_rocket, "target": _ico_target}


def draw_icon(fig, name, cx, cy, size_in=0.42, color="#000000"):
    """Line icon centred at figure fraction (cx, cy)."""
    w = size_in / fig.get_figwidth()
    hgt = size_in / fig.get_figheight()
    a = fig.add_axes([cx - w / 2, cy - hgt / 2, w, hgt])
    a.set_xlim(0, 1)
    a.set_ylim(0, 1)
    a.axis("off")
    ICONS[name](a, dict(facecolor="none", edgecolor=color, linewidth=1.0))
    return a


def _rich_tokens(name, note):
    toks = []
    if name:
        toks.append((name, "bold", "accent"))
    bold = False
    for part in re.split(r"(\*\*)", note or ""):
        if part == "**":
            bold = not bold
        elif part:
            for w in re.findall(r"[⺀-鿿＀-￯]|\n|[^\s⺀-鿿＀-￯]+\s*|\s+", part):
                toks.append((w, "bold" if bold else "normal", "ink"))
    return toks


def rich_text(ax, x, y, name=None, note="", width=1.6, fontsize=9.6, accent="#1F3C88",
              ink="#000000", ha="left", line_gap=1.22):
    """Wrapped annotation whose lead-in is coloured and whose **marked** words are bold.

    (x, y) is the top-left in data coords; width is in inches."""
    fig = ax.figure
    rend = fig.canvas.get_renderer()
    x0, y0 = ax.transData.transform((x, y))
    maxw = width * fig.dpi
    line_h = fontsize * line_gap * fig.dpi / 72
    cx, cy = 0.0, 0.0
    inv = fig.transFigure.inverted()
    arts = []

    def _w(txt, weight):
        t = fig.text(0, 0, txt, fontsize=fontsize, fontweight=weight)
        w = t.get_window_extent(rend).width
        t.remove()
        return w

    space = _w("a a", "normal") - _w("aa", "normal")
    for word, weight, col in _rich_tokens(name, note):
        if word == "\n":
            cx, cy = 0.0, cy + line_h
            continue
        core = word.strip()
        if not core:
            cx += space if cx else 0
            continue
        t = fig.text(0, 0, core, fontsize=fontsize, fontweight=weight,
                     color=accent if col == "accent" else ink, ha="left", va="top", zorder=9,
                     bbox=dict(fc="white", ec="none", pad=0.8))
        w = t.get_window_extent(rend).width
        if cx > 0 and cx + w > maxw:
            cx, cy = 0.0, cy + line_h
        t.set_position(inv.transform((x0 + cx, y0 - cy)))
        cx += w + (space if word != core else 0)
        arts.append(t)
    return arts, (cy + line_h) / fig.dpi           # artists, block height in inches


def capability_ladder(timeline, stages, curve, milestones=None, title=None, source=None,
                      number=None, accent=None, out=None, figsize=(10.2, 6.6), tick_every=None):
    """A staircase of stages on the left, a dotted trajectory climbing through them, and
    annotated milestones hanging off the curve.

    timeline: x labels (dates as strings).
    stages: [{"label": "Vibe Coding", "icon": "coder", "y": 2.0}, ...] bottom → top.
    curve: [[x-label-or-index, y], ...] control points of the trajectory.
    milestones: [{"at": x, "name": "GLM-5:", "note": "A leap into **agentic engineering**",
                  "text": [x, y], "width": 1.7}]  — "text" is the note's top-left corner;
                  omit "note" for a bare label that sits on the curve."""
    setup_fonts()
    M = MONO
    accent = accent or M["navy"]
    _check_cjk(title, source, *[s["label"] for s in stages])
    fig = plt.figure(figsize=figsize, facecolor="white")
    fh = fig.get_figheight()
    pt = 1 / 72 / fh
    y_top = 0.965
    title = _numbered(title, number)
    if title:
        fig.text(0.04, y_top, title, fontsize=14.5, fontweight="bold", color=M["ink"], ha="left", va="top")
        y_top -= 30 * pt
        fig.add_artist(Line2D([0.04, 0.96], [y_top, y_top], color=M["rule"], linewidth=0.9,
                              transform=fig.transFigure))
    y_bot = 0.03
    if source:
        fig.add_artist(Line2D([0.04, 0.96], [0.085, 0.085], color=M["rule"], linewidth=0.9,
                              transform=fig.transFigure))
        fig.text(0.04, 0.045, source, fontsize=11, color=M["ink"], ha="left", va="center")
        y_bot = 0.085
    ax = fig.add_axes([0.165, y_bot + 0.125, 0.78, y_top - y_bot - 0.165])
    n = len(timeline)
    ys = [s["y"] for s in stages]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1
    ax.set_xlim(0, n - 1)
    ax.set_ylim(lo - span * 0.06, hi + span * 0.115)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#7F7F7F")
    ax.spines["bottom"].set_linewidth(1.3)
    ax.set_yticks([])
    every = tick_every or max(1, int(np.ceil(n / 30)))
    idx = list(range(0, n, every))
    ax.set_xticks(idx)
    ax.set_xticklabels([timeline[i] for i in idx], rotation=90, fontsize=9.5, color="#8C8C8C")
    ax.tick_params(axis="x", length=4, width=1.1, color="#7F7F7F", pad=5)
    # trajectory
    cx = np.array([_xpos(timeline, p[0]) for p in curve])
    cy = np.array([p[1] for p in curve], dtype=float)
    xx = np.linspace(cx.min(), cx.max(), 500)
    yy = np.interp(xx, cx, cy)
    ax.plot(xx, yy, color="#8C8C8C", linewidth=2.3, linestyle=(0, (0.9, 1.5)), zorder=4,
            dash_capstyle="butt")
    yat = lambda xv: float(np.interp(xv, cx, cy))  # noqa: E731
    # stages: dashed level line from the label to where the curve crosses it
    fig.canvas.draw()
    to_fig = lambda xd, yd: fig.transFigure.inverted().transform(ax.transData.transform((xd, yd)))  # noqa: E731
    for s in stages:
        if s["y"] > lo:
            ax.plot([-0.03, 1.0], [s["y"], s["y"]], transform=ax.get_yaxis_transform(),
                    color="#BDBDBD", linewidth=1.4, linestyle=(0, (5, 3.2)), zorder=1, clip_on=False)
        fx, fy = to_fig(0, s["y"])
        fig.text(0.092, fy, s["label"], fontsize=10.5, fontweight="bold", color=M["ink"],
                 ha="center", va="center", zorder=5,
                 bbox=dict(fc="white", ec="none", pad=1.2))
        above = [o["y"] for o in stages if o["y"] > s["y"]]
        room = (to_fig(0, min(above))[1] - fy) / pt - 18 if above else 60    # points free above
        size = min(0.36, (room - 12) / 72)
        if s.get("icon") and size >= 0.2:
            draw_icon(fig, s["icon"], 0.092, fy + (11 + size * 36) * pt, size)
    # milestones
    fig.canvas.draw()
    for m in milestones or []:
        xv = _xpos(timeline, m["at"])
        yv = m.get("y", yat(xv))
        if not m.get("note"):
            ax.annotate(m["name"], (xv, yv), xytext=(3, -4), textcoords="offset points",
                        fontsize=10.5, fontweight="bold", color=accent,
                        ha=m.get("ha", "left"), va="top", zorder=8)
            continue
        tx, ty = m["text"]
        tx = _xpos(timeline, tx)
        width = m.get("width", 1.7)
        _arts, h_in = rich_text(ax, tx, ty, m["name"] + " ", m["note"], width=width, accent=accent)
        # leader from the note's nearest edge to the curve
        p0 = ax.transData.transform((tx, ty))
        w_px, h_px = width * fig.dpi, h_in * fig.dpi
        tgt = ax.transData.transform((xv, yv))
        corners = [(p0[0] + w_px + 4, p0[1] - h_px * 0.55), (p0[0] - 4, p0[1] - h_px * 0.5),
                   (p0[0] + w_px * 0.4, p0[1] - h_px - 3), (p0[0] + w_px * 0.4, p0[1] + 3)]
        a = min(corners, key=lambda c: (c[0] - tgt[0]) ** 2 + (c[1] - tgt[1]) ** 2)
        (ax_d, ay_d) = ax.transData.inverted().transform(a)
        ax.plot([ax_d, xv], [ay_d, yv], color="#C4C4C4", linewidth=0.9, zorder=3, clip_on=False)
    return _save(fig, out)


# --------------------------------------------------------------------------
# Shared emphasis: marks (dashed box, red cross, pin, numbered dot), era strip, side notes
# --------------------------------------------------------------------------
_DASH = (0, (4, 3))


def _alert(T):
    return T.get("alert", "#E84A47")


def _badge(owner, xv, yv, n, transform, color="#000000", size=8.5):
    """A numbered dot. owner is an Axes or a Figure."""
    return owner.text(xv, yv, str(n), transform=transform, ha="center", va="center", fontsize=size,
                      fontweight="bold", color=color, zorder=9, clip_on=False,
                      bbox=dict(boxstyle="circle,pad=0.22", fc="white", ec=color, lw=0.9))


def _draw_marks(ax, x, marks, values=None, T=None):
    """Draw emphasis marks on an axes whose x positions are category indices.

    {"type": "box",   "from": x, "to": x, "y": [lo, hi], "text": "…", "text_at": "top"|"bottom"}
    {"type": "cross", "from": x, "to": x, "y": [lo, hi], "text": "…"}
    {"type": "pin",   "at": x, "y": v | "series": name, "text": "…", "dy": 26}
    {"type": "num",   "at": x, "y": v, "n": 1}
    Omit "y" on a box or cross to cover the full plot height. Positions are labels or indices."""
    if not marks:
        return
    T = T or MONO
    red, ink = _alert(T), T["ink"]
    xl = list(x) if x is not None else []
    blend = ax.get_xaxis_transform()
    for m in marks:
        kind = m.get("type", "box")
        if kind not in ("box", "cross", "pin", "num"):
            raise SystemExit(f"marks: unknown type {kind!r}; use box, cross, pin or num")
        if kind in ("box", "cross"):
            pad = m.get("pad", 0.42)
            a, b = _xpos(xl, m["from"]), _xpos(xl, m.get("to", m["from"]))
            lim0, lim1 = sorted(ax.get_xlim())
            x0, x1 = max(lim0, min(a, b) - pad), min(lim1, max(a, b) + pad)
            if m.get("y") is None:
                tr, y0, y1 = blend, 0.02, 0.98
            else:
                tr, (y0, y1) = ax.transData, sorted(float(v) for v in m["y"])
            if kind == "box":
                ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, transform=tr, fill=False,
                                       ec=red, lw=1.3, ls=_DASH, zorder=7, clip_on=False))
            else:
                for (p, q) in (((x0, y0), (x1, y1)), ((x0, y1), (x1, y0))):
                    ax.plot([p[0], q[0]], [p[1], q[1]], transform=tr, color=red, lw=3.4, alpha=0.72,
                            solid_capstyle="round", zorder=7, clip_on=False)
            if m.get("text") and kind == "cross":
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                ax.text(cx, cy, m["text"], transform=tr, ha="center", va="center", fontsize=9.5,
                        color=red, fontweight="bold", zorder=9, clip_on=False, linespacing=1.2,
                        bbox=dict(boxstyle="round,pad=0.35,rounding_size=0.3", fc="white", ec=red,
                                  lw=0.9))
            elif m.get("text"):
                top = m.get("text_at", "top") == "top"
                ax.annotate(m["text"], (x0, y1 if top else y0), xycoords=tr,
                            xytext=(5, -4 if top else 4), textcoords="offset points",
                            ha="left", va="top" if top else "bottom", fontsize=9.5, color=red,
                            fontweight="bold", linespacing=1.2, zorder=9, annotation_clip=False,
                            path_effects=[pe.withStroke(linewidth=3, foreground="white")])
            continue
        xv = _xpos(xl, m["at"])
        yv = m.get("y")
        if yv is None and values:
            arr = values.get(m.get("series"), next(iter(values.values())))
            yv = float(np.asarray(arr, dtype=float)[int(round(xv))])
        if yv is None:
            raise SystemExit(f"marks: {kind} at {m['at']!r} needs a 'y' value")
        if kind == "num":
            _badge(ax, xv, yv, m.get("n", 1), ax.transData, color=ink)
            continue
        dy = m.get("dy", 26)
        ax.plot([xv], [yv], "o", ms=4.2, color=ink, zorder=8, clip_on=False)
        soft = "#EEF4F5" if T is TEAL else "#F2F5FB"
        edge = "#B9D3D9" if T is TEAL else "#C9D3EA"
        ax.annotate(m["text"], (xv, yv), xytext=(m.get("dx", 0), dy), textcoords="offset points",
                    ha="center", va="bottom" if dy >= 0 else "top", fontsize=8.8, color=ink,
                    linespacing=1.15, zorder=9, annotation_clip=False,
                    bbox=dict(boxstyle="round,pad=0.3,rounding_size=0.3", fc=soft, ec=edge, lw=0.8),
                    arrowprops=dict(arrowstyle="-", color=edge, lw=0.9, shrinkA=0, shrinkB=3))


def _draw_eras(ax, x, eras, color="#000000", lines=False):
    """A strip above the plot that names the eras a series went through.
    eras: [{"from": x, "label": "云时代"}, …, {"from": x, "to": x, "label": "广告时代？", "open": true}]
    Each era lasts until the next one starts; the last one runs to its "to" or to the end of x."""
    xl = list(x)
    tr = ax.get_xaxis_transform()
    y = 1.045
    starts = [_xpos(xl, e["from"]) for e in eras]
    last = eras[-1]
    end = _xpos(xl, last["to"]) if last.get("to") is not None else len(xl) - 1
    bounds = starts + [end]
    ax.plot([bounds[0], bounds[-1]], [y, y], transform=tr, color=color, lw=1.1, clip_on=False, zorder=6)
    if last.get("open"):
        ax.annotate("", xy=(bounds[-1] + 0.02 * len(xl), y), xytext=(bounds[-1] - 0.001, y),
                    xycoords=tr, arrowprops=dict(arrowstyle="-|>", color=color, lw=1.1,
                                                 mutation_scale=11), annotation_clip=False)
    for i, b in enumerate(bounds):
        if i == len(bounds) - 1 and last.get("open"):
            continue
        ax.plot([b, b], [y - 0.022, y + 0.022], transform=tr, color=color,
                lw=2.2 if 0 < i < len(bounds) - 1 else 1.1, clip_on=False, zorder=6)
        if lines and 0 < i < len(bounds) - 1:
            ax.axvline(b, color="#BDBDBD", lw=0.9, ls=(0, (2, 2)), zorder=1)
    for e, a, b in zip(eras, bounds[:-1], bounds[1:]):
        ax.text((a + b) / 2, y, e["label"], transform=tr, ha="center", va="center", fontsize=9,
                color=color, zorder=7, clip_on=False,
                bbox=dict(boxstyle="square,pad=0.28", fc="white", ec=color, lw=0.8))


def _side_notes(fig, ax, notes, title=None, numbered=True, fontsize=9.2):
    """Numbered notes in the column _frame_mono(side=…) reserved on the right."""
    x0, x1, ytop, ybot = ax._ic_side
    fh, fw = fig.get_figheight(), fig.get_figwidth()
    pt_y, pt_x = 1 / 72 / fh, 1 / 72 / fw
    ink = MONO["ink"]
    for fs in (fontsize, fontsize - 0.8, fontsize - 1.4):
        arts = []
        units = int((x1 - x0) * fw * 72 * 2 / fs) - (6 if numbered else 4)
        y = ytop - 8 * pt_y
        if title:
            for ln in _wrap(title, units + 2):
                arts.append(fig.text(x0 + 7 * pt_x, y, ln, fontsize=fs + 0.8, fontweight="bold",
                                     color=MONO["navy"], ha="left", va="top"))
                y -= (fs + 0.8) * 1.3 * pt_y
            y -= 5 * pt_y
        for i, note in enumerate(notes):
            n, body = (note.get("n", i + 1), note["text"]) if isinstance(note, dict) else (i + 1, note)
            lines = _wrap_soft(body, units)
            tx = x0 + (7 + (fs * 1.7 if numbered else fs)) * pt_x
            if numbered:
                arts.append(_badge(fig, x0 + (7 + fs * 0.6) * pt_x, y - fs * 0.78 * pt_y, n,
                                   fig.transFigure, color=ink, size=fs - 1.2))
            else:
                arts.append(fig.text(x0 + 7 * pt_x, y, "·", fontsize=fs, color=ink, ha="left", va="top"))
            arts.append(fig.text(tx, y, "\n".join(lines), fontsize=fs, color=ink, ha="left", va="top",
                                 linespacing=1.35))
            y -= (len(lines) * fs * 1.35 + 7) * pt_y
        if y > ybot or fs == fontsize - 1.4:
            if y < ybot:
                warnings.warn("side notes overflow their column; shorten them", stacklevel=3)
            low = max(ybot, y - 4 * pt_y)
            fig.add_artist(Rectangle((x0, low), x1 - x0, ytop - low, transform=fig.transFigure,
                                     fill=False, ec="#BFBFBF", lw=0.8, ls=(0, (3, 2))))
            return
        for a in arts:
            a.remove()


def _legend_under(ax, handles, names, fontsize=9.5, ncol=None):
    """Legend centred just below the x tick labels (re-run after the axes is resized)."""
    fig = ax.figure
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    bb = [t.get_window_extent(rend) for t in ax.get_xticklabels() if t.get_text()]
    y_px = min(b.y0 for b in bb) if bb else ax.get_window_extent(rend).y0
    y_ax = ax.transAxes.inverted().transform((0, y_px - 4))[1]
    if ax.get_legend():
        ax.get_legend().remove()
    return ax.legend(handles, names, loc="upper center", bbox_to_anchor=(0.5, y_ax), frameon=False,
                     ncol=ncol or len(names), fontsize=fontsize, handlelength=1.8, columnspacing=1.6,
                     labelcolor=MONO["legend"], borderaxespad=0)


def _fit_with_legend(ax, handles, names, ncol=None, twins=()):
    for _ in range(2):
        _legend_under(ax, handles, names, ncol=ncol)
        _fit(ax, *twins)


def _prep_notes(notes, figsize, side=0.34):
    """Widen the figure for a notes column so the chart itself keeps its size."""
    if not notes:
        return figsize, 0.0
    return (figsize[0] / (1 - side * 0.92), figsize[1]), side


# --------------------------------------------------------------------------
# Recipe 8 — phases: lines split by dashed boxes, each with a verdict
# --------------------------------------------------------------------------
def phase_trend(x, series, phases, title=None, source=None, unit=None, number=None, yfmt=None,
                ylim=None, labels="phase_ends", label_fmt=None, colors=None, box_color="#9A9A9A",
                eras=None, marks=None, xtick_every=None, out=None, figsize=(9.6, 5.6)):
    """Lines over a long history, cut into phases by dashed boxes. Each phase gets a name, a red
    one-line verdict and up to three bullets, written into the emptier half of its box.

    phases: [{"from": "1995", "to": "2000", "name": "第一阶段（1995-2000）：",
              "verdict": "创造流量，跑通模式", "notes": ["…", "…"], "pos": "auto"}]
    labels: "phase_ends" labels the first series where each phase ends, "ends" only the first
            and last points, None nothing."""
    M = MONO
    _check_cjk(title, source, unit, *series,
               *[str(p.get("name", "")) + str(p.get("verdict", "")) for p in phases])
    fig, ax = _frame_mono(figsize, _numbered(title, number), source, unit)
    x = list(x)
    n = len(x)
    xs = np.arange(n)
    cols = colors or [M["navy"], "#595959", "#A6A6A6", "#C8C8C8"]
    vals, handles = {}, []
    for i, (name, v) in enumerate(series.items()):
        a = np.array([np.nan if t is None else t for t in v], dtype=float)
        vals[name] = a
        (ln,) = ax.plot(xs[:len(a)], a, color=cols[i % len(cols)], lw=2.3 if i == 0 else 1.8,
                        zorder=4.5 if i == 0 else 4, solid_joinstyle="round")
        handles.append(ln)
    ax.set_xlim(-0.6, n - 0.4)
    allv = np.concatenate([a[~np.isnan(a)] for a in vals.values()])
    lo, hi = float(allv.min()), float(allv.max())
    span = (hi - lo) or 1.0
    ax.set_ylim(*(ylim or ((0 if 0 <= lo < span * 0.5 else lo - span * 0.08), hi + span * 0.08)))
    ax.yaxis.set_major_locator(MaxNLocator(8, steps=[1, 2, 2.5, 5, 10]))
    ax.yaxis.set_major_formatter(_tickfmt(yfmt))
    long = n > 14 or max(len(str(s)) for s in x) > 6
    _thin_xticks(ax, x, xtick_every, rotation=45 if long else 0, color=M["tick"], size=9.5)
    if eras:
        _draw_eras(ax, x, eras, color=M["ink"])
    _fit_with_legend(ax, handles, list(series))

    # lay out the phase text, then make head-room for it
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    bb = ax.get_window_extent(rend)
    px_x = bb.width / (ax.get_xlim()[1] - ax.get_xlim()[0])
    ax_h_pt = bb.height * 72 / fig.dpi
    fs_h, fs_n, lsp = 9.4, 8.7, 1.32
    plans = []
    for p in phases:
        x0 = _xpos(x, p["from"]) - 0.42
        x1 = _xpos(x, p.get("to", p["from"])) + 0.42
        w_pt = (x1 - x0) * px_x * 72 / fig.dpi - 10
        head_units = int(w_pt * 2 / fs_h)
        name, verdict = str(p.get("name", "")), str(p.get("verdict", ""))
        wid = lambda t: sum(2 if _CJK.match(c) else 1 for c in t)  # noqa: E731
        rows = []                                    # (text, size, colour, bold, x-offset key)
        if name and verdict and wid(name + verdict) <= head_units:
            rows.append(("pair", name, verdict))
        else:
            rows += [("head", ln) for ln in _wrap(name, head_units)]
            rows += [("verdict", ln) for ln in _wrap(verdict, head_units)]
        note_units = int(w_pt * 2 / fs_n) - 2
        for note in p.get("notes", [])[:3]:
            for k, ln in enumerate(_wrap_soft(note, note_units)):
                rows.append(("note", ("· " if k == 0 else "  ") + ln))
        h_pt = sum((fs_n if r[0] == "note" else fs_h) * lsp for r in rows) + 8
        i0, i1 = max(0, int(np.ceil(x0))), min(n - 1, int(np.floor(x1)))
        seg = np.concatenate([a[i0:i1 + 1] for a in vals.values()])
        seg = seg[~np.isnan(seg)]
        plans.append(dict(p=p, x0=x0, x1=x1, rows=rows, bf=h_pt / ax_h_pt,
                          vmax=float(seg.max()) if len(seg) else hi,
                          vmin=float(seg.min()) if len(seg) else lo))
    gap = 0.07 if labels else 0.04
    y0, y1 = ax.get_ylim()
    frac = lambda v, a, b: (v - a) / (b - a)  # noqa: E731
    for q in plans:
        want = q["p"].get("pos", "auto")
        if want == "auto":
            want = "top" if 0.98 - frac(q["vmax"], y0, y1) >= frac(q["vmin"], y0, y1) - 0.02 else "bottom"
        q["pos"] = want
    if not ylim:
        for _ in range(4):
            for q in plans:
                if q["pos"] == "top":
                    room = 0.97 - q["bf"] - gap
                    if room > 0.15:
                        y1 = max(y1, y0 + (q["vmax"] - y0) / room)
                else:
                    c = 0.03 + q["bf"] + gap * 0.6
                    if c < 0.85:
                        y0 = min(y0, (q["vmin"] - c * y1) / (1 - c))
            if labels:
                y1 = max(y1, y0 + (hi - y0) / 0.90)
        ax.set_ylim(y0, y1)
    pt_ax = 1 / ax_h_pt
    dx = 6 * fig.dpi / 72 / px_x
    for q in plans:
        ax.add_patch(Rectangle((q["x0"], 0.015), q["x1"] - q["x0"], 0.97, transform=ax.get_xaxis_transform(),
                               fill=False, ec=box_color, lw=1.15, ls=_DASH, zorder=2))
        yy = 0.975 - 4 * pt_ax if q["pos"] == "top" else 0.03 + q["bf"] - 4 * pt_ax
        tr = ax.get_xaxis_transform()
        for r in q["rows"]:
            size = fs_n if r[0] == "note" else fs_h
            if r[0] == "pair":
                t = ax.text(q["x0"] + dx, yy, r[1], transform=tr, fontsize=fs_h, fontweight="bold",
                            color=M["ink"], ha="left", va="top", zorder=8)
                fig.canvas.draw()
                w = t.get_window_extent(fig.canvas.get_renderer()).width / px_x
                ax.text(q["x0"] + dx + w, yy, r[2], transform=tr, fontsize=fs_h, fontweight="bold",
                        color=M["alert"], ha="left", va="top", zorder=8)
            else:
                ax.text(q["x0"] + dx, yy, r[1], transform=tr, fontsize=size, ha="left", va="top",
                        fontweight="normal" if r[0] == "note" else "bold", zorder=8,
                        color=M["alert"] if r[0] == "verdict" else M["ink"])
            yy -= size * lsp * pt_ax
    first = next(iter(vals))
    lab = fmt(label_fmt or yfmt)
    a = vals[first]
    ok = np.where(~np.isnan(a))[0]
    idx = []
    if labels == "ends" and len(ok):
        idx = [ok[0], ok[-1]]
    elif labels == "phase_ends" and len(ok):
        idx = [ok[0]] + [int(round(_xpos(x, p.get("to", p["from"])))) for p in phases]
    for i in sorted(set(i for i in idx if 0 <= i < n and not np.isnan(a[i]))):
        ax.plot([i], [a[i]], "o", ms=3.6, color=cols[0], zorder=6)
        ax.annotate(lab(a[i]), (i, a[i]), xytext=(0, 6), textcoords="offset points", ha="center",
                    va="bottom", fontsize=8.6, fontweight="bold", color=cols[0], zorder=7,
                    path_effects=[pe.withStroke(linewidth=2.4, foreground="white")])
    if any(v < 0 for v in allv) and ax.get_ylim()[0] < 0:
        ax.axhline(0, color="#9E9E9E", lw=0.9, zorder=2.5)
    _draw_marks(ax, x, marks, vals)
    return _save(fig, out)


# --------------------------------------------------------------------------
# Recipe 9 — waterfall (bridge from one total to another)
# --------------------------------------------------------------------------
def _draw_waterfall(ax, steps, value_fmt=None, highlight=None, connectors=True, note=None, marks=None):
    M = MONO
    vf = fmt(value_fmt)
    n = len(steps)
    labels = [s["label"] for s in steps]
    hl = set([highlight] if isinstance(highlight, str) else (highlight or []))
    cum, after, lows, highs = 0.0, [], [], []
    texts = []
    for i, s in enumerate(steps):
        kind = s.get("kind", "delta")
        if kind not in ("delta", "total", "subtotal"):
            raise SystemExit(f"waterfall: step {s['label']!r} has kind {kind!r}; use delta, total or subtotal")
        if kind == "total" and s.get("value") is not None:
            cum = float(s["value"])
        if kind in ("total", "subtotal"):
            b0, b1, shown = min(0, cum), max(0, cum), cum
            c = "#7F7F7F"
        else:
            v = float(s["value"])
            b0, b1 = (cum, cum + v) if v >= 0 else (cum + v, cum)
            cum += v
            shown = v
            c = M["greys"][0]
        if s["label"] in hl:
            c = M["navy"] if kind != "delta" else M["highlight"]
        ax.bar(i, b1 - b0, bottom=b0, width=0.56, color=c, zorder=3)
        after.append(cum)
        lows.append(b0)
        highs.append(b1)
        neg = kind == "delta" and shown < 0
        txt = vf(shown) if kind != "delta" or shown < 0 else "+" + vf(shown)
        texts.append(ax.annotate(txt, (i, b1), xytext=(0, 4), textcoords="offset points", ha="center",
                                 va="bottom", fontsize=9.6, color=M["alert"] if neg else M["ink"],
                                 fontweight="bold" if kind != "delta" else "normal", zorder=6))
        if s.get("tag"):
            ax.annotate(s["tag"], (i, b1), xytext=(0, 18), textcoords="offset points", ha="center",
                        va="bottom", fontsize=9, fontweight="bold", color=M["alert"], zorder=6)
    if connectors:
        for i in range(n - 1):
            ax.plot([i + 0.28, i + 0.72], [after[i], after[i]], color="#8C8C8C", lw=0.8,
                    ls=(0, (2, 2)), zorder=2.5)
    top = max(highs) or 1
    bot = min(0, min(lows))
    ax.set_ylim(bot - (top - bot) * 0.04 if bot < 0 else 0, top + (top - bot) * 0.2)
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_xticks(range(n))
    ax.set_xticklabels(["\n".join(_wrap(t, 10)) for t in labels], fontsize=9.5, color=M["tick"],
                       linespacing=1.1)
    ax.yaxis.set_major_locator(MaxNLocator(7, steps=[1, 2, 2.5, 5, 10]))
    ax.yaxis.set_major_formatter(_tickfmt(value_fmt if value_fmt in (None, ",", "$", "%") else None))
    if bot < 0:
        ax.axhline(0, color=M["ink"], lw=0.9, zorder=2)
    if note:
        ax.text(0.98, 0.95, note, transform=ax.transAxes, fontsize=10, color=M["alert"], ha="right",
                va="top", linespacing=1.35)
    _draw_marks(ax, labels, marks, {"after": after})


def waterfall(steps, title=None, source=None, unit=None, number=None, value_fmt=None,
              highlight=None, connectors=True, note=None, marks=None, notes=None, notes_title=None,
              out=None, figsize=(7.2, 4.9)):
    """Bridge from one total to another through the pieces that add or take away.

    steps: [{"label": "零售业务", "value": 187.5, "kind": "total"},
            {"label": "新业务亏损", "value": -49.7},
            {"label": "零售 EBIT", "kind": "subtotal", "tag": "利润率 2.5%"}, …]
    kind: "delta" (default), "subtotal" (running sum so far) or "total" (given value, or running sum)."""
    _check_cjk(title, source, unit, *[s["label"] for s in steps])
    figsize, side = _prep_notes(notes, figsize)
    fig, ax = _frame_mono(figsize, _numbered(title, number), source, unit, side=side)
    _draw_waterfall(ax, steps, value_fmt, highlight, connectors, note, marks)
    _fit(ax)
    if notes:
        _side_notes(fig, ax, notes, notes_title)
    return _save(fig, out)


# --------------------------------------------------------------------------
# Recipe 10 — aligned comparison: put two histories on the same "year N" axis
# --------------------------------------------------------------------------
def _draw_aligned(ax, series, xlabel="Y{n}", yfmt=None, ylim=None, labels="ends", value_fmt=None,
                  colors=None, marks=None, legend=True):
    M = MONO
    cols = colors or [M["navy"], M["salmon"], M["line"], M["greys"][1]]
    n = max(len(s["values"]) for s in series.values())
    x = [xlabel.format(n=i + 1) for i in range(n)]
    xs = np.arange(n)
    vf = fmt(value_fmt or yfmt)
    handles, names, vals = [], [], {}
    for i, (name, s) in enumerate(series.items()):
        v = np.array([np.nan if a is None else a for a in s["values"]], dtype=float)
        vals[name] = v
        c = cols[i % len(cols)]
        k = len(v)
        periods = s.get("periods")
        start = s.get("start")
        f = s.get("forecast_from")
        if periods:
            fi = periods.index(f) if f is not None else None
            span = f"{periods[0]}-{periods[-1]}"
        elif isinstance(start, (int, float)):
            fi = int(f - start) if f is not None else None
            span = f"{int(start)}-{int(start) + k - 1}{'E' if f is not None else ''}"
        else:
            fi, span = None, None
        solid_end = k if fi is None else fi
        ax.plot(xs[:solid_end], v[:solid_end], color=c, lw=2.1, zorder=4, marker="o", ms=3.2)
        if fi is not None and fi < k:
            j = max(0, fi - 1)
            ax.plot(xs[j:k], v[j:k], color=c, lw=1.8, ls=(0, (3, 2)), zorder=4, marker="o", ms=3.2,
                    markerfacecolor="white")
        handles.append(Line2D([0], [0], color=c, lw=2.1))
        cjk = _CJK.search(str(name))
        names.append(name if not span else (f"{name}（{span}）" if cjk else f"{name} ({span})"))
        ok = np.where(~np.isnan(v))[0]
        pick = list(ok) if labels == "all" else ([ok[0], ok[-1]] if labels == "ends" and len(ok) else [])
        for j in pick:
            above = i % 2 == 0
            ax.annotate(vf(v[j]), (j, v[j]), xytext=(0, 6 if above else -7), textcoords="offset points",
                        ha="center", va="bottom" if above else "top", fontsize=8.6, color=c,
                        fontweight="bold", zorder=6,
                        path_effects=[pe.withStroke(linewidth=2.4, foreground="white")])
    ax.set_xlim(-0.4, n - 0.6)
    ax.set_xticks(xs)
    ax.set_xticklabels(x, fontsize=9.5, color=M["tick"])
    if ylim:
        ax.set_ylim(*ylim)
    else:
        allv = np.concatenate([a[~np.isnan(a)] for a in vals.values()])
        lo, hi = float(allv.min()), float(allv.max())
        pad = (hi - lo) * 0.10 or 1
        ax.set_ylim(0 if 0 <= lo < 0.6 * hi else lo - pad, hi + pad)
    ax.yaxis.set_major_formatter(_tickfmt(yfmt))
    ax.yaxis.set_major_locator(MaxNLocator(7, steps=[1, 2, 2.5, 5, 10]))
    if legend:
        ax.legend(handles, names, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=len(names),
                  frameon=False, fontsize=9.5, handlelength=1.9, columnspacing=1.6)
    _draw_marks(ax, x, marks, vals)


def aligned_compare(series, title=None, source=None, unit=None, number=None, xlabel="Y{n}",
                    yfmt=None, ylim=None, labels="ends", value_fmt=None, colors=None, marks=None,
                    notes=None, notes_title=None, out=None, figsize=(7.2, 4.9)):
    """Compare companies at the same stage of their life, not on the same calendar.

    series: {"A 公司": {"start": 2011, "values": [...], "forecast_from": 2020},
             "B 公司": {"start": 2003, "values": [...]}}
    Each series is re-indexed to year 1, 2, 3… of its own history; the legend keeps the real years.
    Give "periods": ["FY11", …] instead of "start" when the periods are not plain years.
    xlabel: tick text, "Y{n}" by default, "第{n}年" for Chinese."""
    _check_cjk(title, source, unit, *series, xlabel)
    figsize, side = _prep_notes(notes, figsize)
    fig, ax = _frame_mono(figsize, _numbered(title, number), source, unit, side=side)
    _draw_aligned(ax, series, xlabel, yfmt, ylim, labels, value_fmt, colors, marks)
    _fit(ax)
    if notes:
        _side_notes(fig, ax, notes, notes_title)
    return _save(fig, out)


# --------------------------------------------------------------------------
# Recipe 11 — process flow with the cost of each step underneath
# --------------------------------------------------------------------------
def process_cost(steps, title=None, source=None, unit=None, number=None, value_fmt="%1",
                 groups=None, highlight=None, highlight_text=None, out=None, figsize=(9.6, 5.2)):
    """The steps of a process as boxes, each step's cost as a bar directly underneath, one step
    ringed in red where the money (or the room to save it) is.

    steps: [{"label": "顾客下单"}, {"label": "订单处理", "cost": 11.0, "cost_label": "支付手续费"}, …]
    groups: [{"from": "仓储", "to": "打包", "text": "仓内费用 34.7%", "row": "steps" | "bars"}]
    highlight: a step label (or list) to ring; highlight_text: the red line next to the ring."""
    M = MONO
    _check_cjk(title, source, unit, *[s["label"] for s in steps], highlight_text)
    fig, ax = _frame_mono(figsize, _numbered(title, number), source, unit)
    labels = [s["label"] for s in steps]
    n = len(steps)
    costs = np.array([np.nan if s.get("cost") is None else s["cost"] for s in steps], dtype=float)
    hl = [highlight] if isinstance(highlight, str) else list(highlight or [])
    hi_idx = [labels.index(h) for h in hl]
    bmax = np.nanmax(costs) if np.any(~np.isnan(costs)) else 1
    BAR_TOP, BOX_Y, BOX_H = 0.48, 0.82, 0.12
    ax.set_ylim(0, bmax / BAR_TOP)
    ax.set_xlim(-0.6, n - 0.4)
    ax.grid(False)
    ax.set_yticks([])
    vf = fmt(value_fmt)
    for i, v in enumerate(costs):
        if np.isnan(v):
            continue
        c = M["navy"] if i in hi_idx else M["greys"][1]
        ax.bar(i, v, width=0.46, color=c, zorder=3)
        ax.annotate(vf(v), (i, v), xytext=(0, 4), textcoords="offset points", ha="center", va="bottom",
                    fontsize=9.6, fontweight="bold" if i in hi_idx else "normal",
                    color=M["alert"] if i in hi_idx else M["ink"], zorder=6)
    ax.set_xticks(range(n))
    ax.set_xticklabels(["\n".join(_wrap(s.get("cost_label", s["label"]) if s.get("cost") is not None
                                        else "", 10)) for s in steps], fontsize=9.2, color=M["tick"],
                       linespacing=1.1)
    _fit(ax)
    tr = ax.get_xaxis_transform()
    fig.canvas.draw()
    bb = ax.get_window_extent(fig.canvas.get_renderer())
    aspect = (bb.width / (n - 0.4 + 0.6)) / bb.height          # px per x unit / px per axes height
    for i, s in enumerate(steps):
        ring = i in hi_idx
        ax.add_patch(FancyBboxPatch((i - 0.38, BOX_Y - BOX_H / 2), 0.76, BOX_H, transform=tr,
                                    boxstyle="round,pad=0,rounding_size=0.06", mutation_aspect=aspect,
                                    fc="white", ec=M["alert"] if ring else "#8C8C8C",
                                    lw=1.2 if ring else 0.9, zorder=5, clip_on=False))
        ax.text(i, BOX_Y, "\n".join(_wrap(s["label"], 8)), transform=tr, ha="center", va="center",
                fontsize=9, color=M["ink"], zorder=6, linespacing=1.1)
        if i < n - 1:
            ax.annotate("", xy=(i + 0.62, BOX_Y), xytext=(i + 0.38, BOX_Y), xycoords=tr,
                        arrowprops=dict(arrowstyle="-|>", color="#808080", lw=0.9, mutation_scale=9,
                                        shrinkA=0, shrinkB=0), annotation_clip=False)
        if not np.isnan(costs[i]):
            top = costs[i] / (bmax / BAR_TOP) + 0.075
            ax.plot([i, i], [top, BOX_Y - BOX_H / 2 - 0.01], transform=tr, color="#D0D0D0", lw=0.7,
                    ls=(0, (1, 2)), zorder=1)
    for g in groups or []:
        a, b = labels.index(g["from"]), labels.index(g.get("to", g["from"]))
        if g.get("row", "steps") == "steps":
            yb, tick, ty, va = BOX_Y - BOX_H / 2 - 0.05, 0.02, BOX_Y - BOX_H / 2 - 0.065, "top"
        else:
            peak = np.nanmax(costs[a:b + 1]) / (bmax / BAR_TOP)
            yb, tick, ty, va = peak + 0.11, -0.02, peak + 0.125, "bottom"
        ax.plot([a - 0.3, a - 0.3, b + 0.3, b + 0.3], [yb + tick, yb, yb, yb + tick], transform=tr,
                color="#595959", lw=0.9, zorder=4, clip_on=False)
        ax.text((a + b) / 2, ty, g["text"], transform=tr, ha="center", va=va, fontsize=9,
                color=M["ink"], zorder=6, path_effects=[pe.withStroke(linewidth=3, foreground="white")])
    if hi_idx:
        a, b = min(hi_idx), max(hi_idx)
        ax.add_patch(Ellipse(((a + b) / 2, BOX_Y), (b - a) + 1.12, BOX_H * 2.4, transform=tr,
                             fill=False, ec=M["alert"], lw=1.2, ls=_DASH, zorder=4, clip_on=False))
        if highlight_text:
            ax.text((a + b) / 2, BOX_Y + BOX_H * 1.2 + 0.02, highlight_text, transform=tr,
                    ha="center", va="bottom", fontsize=9.6, fontweight="bold", color=M["alert"],
                    zorder=6, clip_on=False)
    _fit(ax)
    return _save(fig, out)


# --------------------------------------------------------------------------
# Recipe 12 — structure compared: 100% columns joined part by part, with numbered notes
# --------------------------------------------------------------------------
def share_compare(columns, parts, title=None, source=None, unit=None, number=None, highlight=None,
                  links=True, numbers=None, notes=None, notes_title=None, value_fmt="%",
                  min_label=4, out=None, figsize=(6.6, 4.9)):
    """Two to four 100% columns side by side, the same part joined by a dashed link, numbered dots
    on the links that the notes on the right explain one by one.

    columns: {"A 公司 2012": [..], "B 公司 2020H": [..]}  values bottom → top, normalised to 100.
    parts: part names bottom → top.  highlight: part name(s) to colour (two at most).
    numbers: {part: n} puts dot n on that part's link.  notes: ["…", "…"] numbered 1, 2, …"""
    M = MONO
    _check_cjk(title, source, unit, *columns, *parts)
    figsize, side = _prep_notes(notes, figsize, side=0.38)
    fig, ax = _frame_mono(figsize, _numbered(title, number), source, unit, side=side)
    names = list(columns)
    k = len(names)
    data = []
    for nm in names:
        v = np.nan_to_num(np.array(columns[nm], dtype=float))
        data.append(v / v.sum() * 100 if v.sum() else v)
    hl = [highlight] if isinstance(highlight, str) else list(highlight or [])
    accent = {p: c for p, c in zip(hl, (M["navy"], M["sky"]))}
    greys = ["#E6E6E6", "#CFCFCF", "#B8B8B8", "#A0A0A0", "#8A8A8A", "#747474", "#5E5E5E"]
    gi = iter(greys)
    cols = [accent.get(p) or next(gi, "#D9D9D9") for p in parts]
    W = 0.40
    centers = {}
    vf = fmt(value_fmt)
    for c_i, v in enumerate(data):
        cum = 0.0
        for j, p in enumerate(parts):
            h = v[j]
            ax.bar(c_i, h, bottom=cum, width=W, color=cols[j], edgecolor="white", lw=0.6, zorder=3)
            if h >= min_label:
                dark = cols[j] in (M["navy"], "#747474", "#5E5E5E", "#8A8A8A")
                ax.text(c_i, cum + h / 2, vf(h), ha="center", va="center", fontsize=9,
                        color="white" if dark else M["ink"], zorder=6,
                        fontweight="bold" if p in accent else "normal")
            centers[(c_i, p)] = cum + h / 2
            cum += h
    marked = set(hl) | set((numbers or {}).keys())
    for j, p in enumerate(parts):
        if links is False or (links == "marked" and p not in marked):
            continue
        for c_i in range(k - 1):
            y_a, y_b = centers[(c_i, p)], centers[(c_i + 1, p)]
            ax.annotate("", xy=(c_i + 1 - W / 2 - 0.02, y_b), xytext=(c_i + W / 2 + 0.02, y_a),
                        arrowprops=dict(arrowstyle="->", color="#9A9A9A", lw=0.8, ls=(0, (3, 2)),
                                        shrinkA=0, shrinkB=0), zorder=4)
    for p, num in (numbers or {}).items():
        y_a, y_b = centers[(0, p)], centers[(1, p)] if k > 1 else centers[(0, p)]
        _badge(ax, 0.5 if k > 1 else W, (y_a + y_b) / 2, num, ax.transData, color=M["ink"])
    # direct labels on the left of the first column, spread so they never touch
    ys = [centers[(0, p)] for p in parts]
    order = np.argsort(ys)
    fig.canvas.draw()
    px_per = ax.get_window_extent(fig.canvas.get_renderer()).height / 100
    min_gap = 11.5 * fig.dpi / 72 / px_per
    placed = list(ys)
    last = -1e9
    for j in order:
        placed[j] = max(placed[j], last + min_gap)
        last = placed[j]
    over = last - 99
    if over > 0:
        placed = [y - over for y in placed]
    for j, p in enumerate(parts):
        xl = -W / 2 - 0.08
        ax.text(xl, placed[j], p, ha="right", va="center", fontsize=9,
                color=M["navy"] if p in accent else M["tick"],
                fontweight="bold" if p in accent else "normal", zorder=6)
        if abs(placed[j] - ys[j]) > 0.5:
            ax.plot([xl + 0.01, -W / 2], [placed[j], ys[j]], color="#BFBFBF", lw=0.6, zorder=2)
    ax.set_xlim(-1.05, k - 0.55)
    ax.set_ylim(0, 100)
    ax.set_yticks([])
    ax.grid(False)
    ax.set_xticks(range(k))
    ax.set_xticklabels(names, fontsize=9.8, color=M["ink"], fontweight="bold")
    _fit(ax)
    if notes:
        _side_notes(fig, ax, notes, notes_title)
    return _save(fig, out)


# --------------------------------------------------------------------------
# Diagram canvas: a mono frame whose plot area is handed over to drawing
# --------------------------------------------------------------------------
def _diagram_canvas(figsize, title, source, number=None, unit=None):
    fig, ax0 = _frame_mono(figsize, _numbered(title, number), source, unit)
    floor, ceil = ax0._ic_bounds
    ax0.remove()
    return fig, (0.04, floor + 0.01, 0.92, ceil - floor - 0.02)


def _two_tone(ax, x, y, first, second, size, transform=None, ha="center", colors=None):
    """'name：' in ink and 'key' in red on one line, centred (or left-aligned) on x."""
    M = MONO
    c1, c2 = colors or (M["ink"], M["alert"])
    tr = transform or ax.transData
    fig = ax.figure
    a = ax.text(x, y, first, transform=tr, fontsize=size, fontweight="bold", color=c1, ha="left",
                va="center", zorder=8)
    b = ax.text(x, y, second, transform=tr, fontsize=size, fontweight="bold", color=c2, ha="left",
                va="center", zorder=8)
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    wa, wb = a.get_window_extent(rend).width, b.get_window_extent(rend).width
    px0 = tr.transform((x, y))[0] - ((wa + wb) / 2 if ha == "center" else 0)
    inv = tr.inverted()
    a.set_x(inv.transform((px0, 0))[0])
    b.set_x(inv.transform((px0 + wa, 0))[0])
    return a, b


# --------------------------------------------------------------------------
# Recipe 13 — flywheel: nodes on a loop around a hub, one or more loops side by side
# --------------------------------------------------------------------------
def _polar(r, th):
    return np.array([r * np.cos(th), r * np.sin(th)])


def _sweep(rA, thA, rB, thB, bulge=0.0, direction="cw", n=220):
    """Points from (rA, thA) to (rB, thB) turning cw/ccw, radius eased linearly plus a bulge."""
    t = np.linspace(0, 1, n)
    if direction == "cw":
        d = (thA - thB) % (2 * np.pi) or 2 * np.pi
        th = thA - d * t
    else:
        d = (thB - thA) % (2 * np.pi) or 2 * np.pi
        th = thA + d * t
    r = rA + (rB - rA) * t + bulge * np.sin(np.pi * t)
    return np.c_[r * np.cos(th), r * np.sin(th)]


def _trim(pts, box_a, box_b):
    """Drop the points that fall inside the start and end label boxes (x0, y0, x1, y1)."""
    def inside(p, b):
        return b is not None and b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]
    i, j = 0, len(pts) - 1
    while i < j and inside(pts[i], box_a):
        i += 1
    while j > i and inside(pts[j], box_b):
        j -= 1
    return pts[i:j + 1]


def _flow(ax, pts, color="#595959", lw=1.2, dashed=False, zorder=2, halo=True):
    """A curve with a solid arrowhead; a white halo makes crossings read as over/under."""
    if len(pts) < 6:
        return
    style = (0, (3.2, 2.2)) if dashed else "-"
    fx = [pe.withStroke(linewidth=lw + 3.2, foreground="white")] if halo else None
    ax.plot(pts[:-3, 0], pts[:-3, 1], color=color, lw=lw, ls=style, solid_capstyle="round",
            zorder=zorder, path_effects=fx)
    ax.add_patch(FancyArrowPatch(tuple(pts[-6]), tuple(pts[-1]), arrowstyle="-|>", mutation_scale=10 + lw * 1.5,
                                 color=color, lw=lw, shrinkA=0, shrinkB=0, zorder=zorder + 0.1))


def _label_boxes(ax, texts, pad=0.05):
    fig = ax.figure
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    out = {}
    for key, t in texts.items():
        bb = t.get_window_extent(rend)
        (x0, y0), (x1, y1) = inv.transform((bb.x0, bb.y0)), inv.transform((bb.x1, bb.y1))
        out[key] = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    return out


def _wheel_frame(ax, wheel, top):
    """Header (two-tone title, bullets) and caption; returns the y where the drawing may start."""
    M = MONO
    y = top - 0.08
    if wheel.get("title") or wheel.get("key"):
        _two_tone(ax, 0, y, wheel.get("title", ""), wheel.get("key", ""), 10.4)
        y -= 0.24
    for b in wheel.get("bullets", []):
        ax.text(-1.42, y, "·  " + b, ha="left", va="center", fontsize=8.8, color=M["ink"], zorder=6)
        y -= 0.17
    cap = wheel.get("caption")
    if cap:
        lines = cap if isinstance(cap, list) else [cap]
        yy = -1.47
        for k, ln in enumerate(lines):
            ax.text(0, yy - k * 0.17, ln, ha="center", va="center", fontsize=9.4, color=M["navy"],
                    zorder=6)
    return y


def _draw_wheel(ax, wheel, hub_color):
    """Loops of nodes around a hub. Nodes shared between loops are placed once, so a second loop
    cuts across the first; links add branches, spokes from the hub and long outside sweeps."""
    M = MONO
    nb = len(wheel.get("bullets", []))
    top = 1.42 + 0.17 * nb
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.68 - (0.17 if isinstance(wheel.get("caption"), list) and len(wheel["caption"]) > 1 else 0),
                top)
    ax.set_aspect("equal")
    ax.axis("off")
    _wheel_frame(ax, wheel, top)
    loops = wheel.get("loops") or [{"nodes": wheel["nodes"], "dashed": wheel.get("dashed", False)}]
    hub_r = wheel.get("hub_r", 0.36)
    pos, edges = {}, {}
    for L in loops:
        names, r = L["nodes"], L.get("r", 1.0)
        start = np.deg2rad(L.get("start", 90))
        for j, nm in enumerate(names):
            pos.setdefault(nm, (r, start - 2 * np.pi * j / len(names)))
        for j, nm in enumerate(names):
            if j == len(names) - 1 and L.get("closed", True) is False:
                break
            nxt = names[(j + 1) % len(names)]
            edges.setdefault((nm, nxt), dict(dashed=L.get("dashed", False), color=L.get("color"),
                                             lw=L.get("lw"), bulge=L.get("bulge", 0.0), dir="cw"))
    for lk in wheel.get("links", []):
        edges[(lk["from"], lk["to"])] = dict(dashed=lk.get("dashed", False), color=lk.get("color"),
                                             lw=lk.get("lw"), bulge=lk.get("bulge", 0.0),
                                             dir=lk.get("dir", "cw"))
    ax.add_patch(Circle((0, 0), hub_r, fc=hub_color, ec="none", zorder=4))
    ax.text(0, 0, "\n".join(_wrap(wheel.get("center", ""), 8)), ha="center", va="center",
            fontsize=10.5, fontweight="bold", color="white", zorder=5, linespacing=1.15)
    texts = {}
    for nm, (r, th) in pos.items():
        texts[nm] = ax.text(r * np.cos(th), r * np.sin(th), "\n".join(_wrap_soft(nm, 16)), ha="center",
                            va="center", fontsize=9.2, color=M["ink"], zorder=7, linespacing=1.15,
                            fontweight="bold" if wheel.get("bold_nodes") else "normal")
    boxes = _label_boxes(ax, texts)
    for (a, b), e in edges.items():
        if a == "center":
            rB, thB = pos[b]
            pts = _sweep(hub_r * 0.5, thB + 0.9 * (1 if e["dir"] == "cw" else -1), rB, thB,
                         e["bulge"], e["dir"])
            pts = _trim(pts, None, boxes[b])
            behind = True
        else:
            (rA, thA), (rB, thB) = pos[a], pos[b]
            pts = _trim(_sweep(rA, thA, rB, thB, e["bulge"], e["dir"]), boxes[a], boxes[b])
            behind = False
        _flow(ax, pts, color=e["color"] or "#4D4D4D", lw=e["lw"] or (1.0 if e["dashed"] else 1.4),
              dashed=e["dashed"], zorder=3 if behind else 2.5)


def _multi_tone(ax, x, y, parts, ha="center", halo=True):
    """Several runs of text on one line: parts = [(text, size, colour, weight), …]."""
    fig = ax.figure
    fx = [pe.withStroke(linewidth=3.2, foreground="white")] if halo else None
    arts = [ax.text(x, y, t, fontsize=sz, color=c, fontweight=w, ha="left", va="baseline", zorder=8,
                    path_effects=fx) for t, sz, c, w in parts if t]
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    widths = [a.get_window_extent(rend).width for a in arts]
    total = sum(widths)
    px = ax.transData.transform((x, y))[0] - {"center": total / 2, "left": 0, "right": total}[ha]
    inv = ax.transData.inverted()
    for a, wd in zip(arts, widths):
        a.set_x(inv.transform((px, 0))[0])
        px += wd
    return arts


def _draw_spiral(ax, wheel, hub_color):
    """Businesses added ring by ring: the hub sits at the bottom and each turn of the spiral is
    wider and higher than the last, so the rings fan out upward like a vase. Each stage's tag and
    name sit on the crown of its own turn."""
    M = MONO
    nb = len(wheel.get("bullets", []))
    top = 1.42 + 0.17 * nb
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.68, top)
    ax.set_aspect("equal")
    ax.axis("off")
    head = _wheel_frame(ax, wheel, top)
    stages = wheel["stages"]
    n = len(stages)
    r0, r1, squash, hub_r = 0.40, 1.36, 0.36, 0.20
    dr = (r1 - r0) / n
    lift = 0.7 * dr
    y_top = head - 0.06                                   # crown of the outermost turn
    cy0 = max(-1.0, y_top - lift * (n - 0.5) - r1)
    ax.add_patch(Circle((0, cy0), hub_r, fc=hub_color, ec="none", zorder=5))
    ax.text(0, cy0, wheel.get("center", ""), ha="center", va="center", fontsize=9.6,
            fontweight="bold", color="white", zorder=6)

    def at(sv):
        th = -np.pi / 2 - 2 * np.pi * sv                  # clockwise, starting at six o'clock
        rr = r0 + dr * sv
        yy = rr * np.sin(th)
        yy = np.where(yy < 0, yy * squash, yy)
        return np.c_[rr * np.cos(th), yy + cy0 + lift * sv]

    shades = ramp(M["navy"], n + 2)[::-1][1:n + 1]       # pale inside, deep outside
    cuts = [0.0] + [k + f for k in range(n) for f in (0.375, 0.75)]     # heads upper-left and right
    for c0, c1 in zip(cuts[:-1], cuts[1:]):
        k = min(n - 1, int((c0 + c1) / 2))
        _flow(ax, at(np.linspace(c0, c1, 120)), color=shades[k], lw=1.0 + 1.5 * k / max(1, n - 1),
              zorder=2 + k * 0.01)
    for k, st in enumerate(stages):
        cx, cyk = at(np.array([k + 0.5]))[0]
        parts = [(st.get("tag", ""), 10.6, M["alert"], "bold"),
                 ("  " + st.get("label", ""), 9.6, M["navy"], "bold")]
        _multi_tone(ax, cx, cyk - 0.04, parts, ha="center")
        if st.get("note"):
            ax.text(cx, cyk - 0.13, st["note"], ha="center", va="center", fontsize=7.8, color="#7F7F7F",
                    zorder=8, path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])


def flywheel(wheels, title=None, source=None, number=None, hub_color=None, out=None, figsize=None):
    """Positive-feedback loops, one or several side by side.

    A wheel is either
      {"title": "收入增长：", "key": "流量飞轮", "center": "增长", "bullets": ["…"],
       "loops": [{"nodes": [...], "r": 1.0, "dashed": true, "start": 120},
                 {"nodes": [...], "r": 0.6}],            # shared names cut across rings
       "links": [{"from": "center" | node, "to": node, "bulge": 0.3, "dir": "cw", "dashed": false}],
       "caption": "…" or ["…", "…"]}
    or a spiral of stages growing outward:
      {"kind": "spiral", "center": "增长", "stages": [{"tag": "2C", "label": "…", "note": "…"}, …]}
    The short form {"nodes": [...]} still draws a single loop."""
    M = MONO
    _check_cjk(title, source, *[str(w.get("title", "")) + str(w.get("key", "")) for w in wheels])
    k = len(wheels)
    figsize = figsize or (4.0 * k + 0.4, 5.4)
    fig, (L, B, W, H) = _diagram_canvas(figsize, title, source, number)
    w = W / k
    for i, wh in enumerate(wheels):
        ax = fig.add_axes([L + i * w, B, w, H])
        if wh.get("kind") == "spiral":
            _draw_spiral(ax, wh, hub_color or M["navy"])
        else:
            _draw_wheel(ax, wh, hub_color or M["navy"])
        if i:
            fig.add_artist(Line2D([L + i * w, L + i * w], [B + H * 0.10, B + H * 0.90], color="#D9D9D9",
                                  lw=0.8, ls=(0, (3, 3)), transform=fig.transFigure))
    return _save(fig, out)


# --------------------------------------------------------------------------
# Recipe 14 — tiers: business models stacked by how easily they turn traffic into money
# --------------------------------------------------------------------------
def tiers(levels, title=None, source=None, number=None, trend=None, highlight=None, links=None,
          out=None, figsize=(9.6, 5.4)):
    """Layers of a concept, top to bottom. Each layer has a tag on the left, a row of items and
    a bracketed verdict on the right; an optional arrow on the far right names the direction.

    levels: [{"label": "第一层", "items": [{"name": "搜索", "note": "流量广告", "size": "千亿美元"}],
              "side": "易变现"}, …]  top → bottom.   trend: "越往下，变现越难".
    links: [{"from": "搜索", "to": "电商", "text": "流量导入", "bend": 0.2, "dashed": true}] —
           red curved arrows between items, so traffic visibly flows from one layer into the next."""
    M = MONO
    _check_cjk(title, source, trend, *[lv.get("label", "") for lv in levels])
    fig, rect = _diagram_canvas(figsize, title, source, number)
    ax = fig.add_axes(rect)
    ax.axis("off")
    n = len(levels)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, n)
    hl = set([highlight] if isinstance(highlight, str) else (highlight or []))
    fig.canvas.draw()
    bb = ax.get_window_extent(fig.canvas.get_renderer())
    aspect = (bb.width / 10) / (bb.height / n)
    x_lo, x_hi = 1.35, 7.85 if trend else 8.35
    where = {}
    for r, lv in enumerate(levels):
        yc = n - r - 0.5
        if r:
            ax.plot([0.1, 9.9], [n - r, n - r], color="#E3E3E3", lw=0.8, zorder=1)
        ax.text(0.15, yc, lv.get("label", ""), ha="left", va="center", fontsize=10.5,
                fontweight="bold", fontstyle="italic", color="#595959")
        items = lv.get("items", [])
        m = max(1, len(items))
        slot = (x_hi - x_lo) / m
        bw = min(2.3, slot - 0.22)
        for j, it in enumerate(items):
            xc = x_lo + slot * (j + 0.5)
            where[it.get("name")] = (xc, yc, bw)
            on = it.get("name") in hl
            ax.add_patch(FancyBboxPatch((xc - bw / 2, yc - 0.34), bw, 0.68,
                                        boxstyle="round,pad=0,rounding_size=0.12",
                                        mutation_aspect=aspect,
                                        fc=M["highlight"] if on else "#F3F5FA",
                                        ec=M["navy"] if on else "#C9D3EA", lw=1.0, zorder=3))
            rows = [(it.get("name", ""), 11, M["navy"], "bold")]
            if it.get("note"):
                rows.append((it["note"], 9, M["alert"], "normal"))
            if it.get("size"):
                rows.append((it["size"], 8, "#808080", "normal"))
            hts = [s * 1.5 for _, s, _, _ in rows]
            total = sum(hts)
            y = yc + total / 2 / (bb.height / n * 72 / fig.dpi)
            for (txt, s, c, wgt), h in zip(rows, hts):
                step = h / (bb.height / n * 72 / fig.dpi)
                ax.text(xc, y - step / 2, txt, ha="center", va="center", fontsize=s, color=c,
                        fontweight=wgt, zorder=4)
                y -= step
        if lv.get("side"):
            xs = x_hi + 0.12
            ax.plot([xs, xs + 0.08, xs + 0.08, xs], [yc + 0.36, yc + 0.36, yc - 0.36, yc - 0.36],
                    color="#8C8C8C", lw=0.9, zorder=2)
            ax.text(xs + 0.2, yc, "\n".join(_wrap(lv["side"], 8)), ha="left", va="center",
                    fontsize=9.5, color=M["ink"], linespacing=1.2)
    for lk in links or []:
        (xa, ya, wa), (xb, yb, wb) = where[lk["from"]], where[lk["to"]]
        if abs(ya - yb) < 1e-9:
            sg = 1 if xb > xa else -1
            p0, p1 = np.array([xa + sg * wa / 2, ya]), np.array([xb - sg * wb / 2, yb])
        else:
            sg = -1 if yb < ya else 1
            p0, p1 = np.array([xa, ya + sg * 0.36]), np.array([xb, yb - sg * 0.36])
        q0, q1 = ax.transData.transform(p0), ax.transData.transform(p1)   # bend in screen space
        d = q1 - q0
        ctrl = (q0 + q1) / 2 + lk.get("bend", 0.15) * np.array([-d[1], d[0]])
        t = np.linspace(0, 1, 120)[:, None]
        pts = ax.transData.inverted().transform((1 - t) ** 2 * q0 + 2 * (1 - t) * t * ctrl + t ** 2 * q1)
        _flow(ax, pts, color=M["alert"], lw=1.0, dashed=lk.get("dashed", True), zorder=3.5, halo=False)
        if lk.get("text"):
            q = pts[len(pts) // 2]
            ax.text(q[0] + 0.08, q[1], lk["text"], ha="left", va="center", fontsize=8.4, color=M["alert"],
                    zorder=6, path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])
    if trend:
        ax.annotate("", xy=(9.75, 0.08), xytext=(9.75, n - 0.08),
                    arrowprops=dict(arrowstyle="-|>", color=M["alert"], lw=1.3, mutation_scale=14))
        cjk = bool(_CJK.search(trend))
        ax.text(9.6, n / 2, "\n".join(trend.replace("，", "")) if cjk else trend, ha="right",
                va="center", rotation=0 if cjk else -90, fontsize=9.6, color=M["alert"],
                fontweight="bold", linespacing=1.05)
    return _save(fig, out)


# --------------------------------------------------------------------------
# Recipe 15 — donuts: structure of one total, or of several totals side by side
# --------------------------------------------------------------------------
_DONUT_GREYS = ["#D9D9D9", "#BDBDBD", "#A3A3A3", "#8A8A8A", "#707070", "#5A5A5A"]


def _donut_colors(parts, highlight):
    hl = [highlight] if isinstance(highlight, str) else list(highlight or [])
    accent = dict(zip(hl, (MONO["navy"], MONO["sky"])))
    greys = iter(_DONUT_GREYS)
    return {p: accent.get(p) or next(greys, "#E6E6E6") for p in parts}


def _draw_donut(ax, parts, values, highlight=None, center=None, value_fmt="%", colors=None,
                subtitle=None, marks=None):
    M = MONO
    v = np.array(values, dtype=float)
    share = v / v.sum() * 100 if v.sum() else v
    cmap = colors or _donut_colors(parts, highlight)
    ax.axis("off")
    ax.set_aspect("equal")
    ax.pie(v, startangle=90, counterclock=False, colors=[cmap[p] for p in parts],
           wedgeprops=dict(width=0.30, edgecolor="white", linewidth=1.4))
    ax.set_xlim(-1.75, 1.75)
    ax.set_ylim(-1.3, 1.42 if subtitle else 1.3)
    if center:
        ax.text(0, 0, center, ha="center", va="center", fontsize=10.5, fontweight="bold",
                color=M["ink"], linespacing=1.2)
    if subtitle:
        ax.text(0, 1.36, subtitle, ha="center", va="center", fontsize=10, fontweight="bold",
                color=M["ink"])
    vf = fmt(value_fmt)
    start = np.pi / 2
    placed = {"L": [], "R": []}
    ends = []
    for p, s in zip(parts, share):
        mid = start - s / 100 * np.pi            # clockwise
        start -= s / 100 * 2 * np.pi
        side = "R" if np.cos(mid) >= 0 else "L"
        ends.append((p, s, mid, side))
    fig = ax.figure
    fig.canvas.draw()
    px_per = ax.get_window_extent(fig.canvas.get_renderer()).height / (ax.get_ylim()[1] - ax.get_ylim()[0])
    gap = 12 * fig.dpi / 72 / px_per
    for side in ("L", "R"):
        group = sorted([e for e in ends if e[3] == side], key=lambda e: -np.sin(e[2]))
        last = 1e9
        for p, s, mid, _ in group:
            y = min(1.12 * np.sin(mid), last - gap)
            last = y
            placed[side].append((p, s, mid, y))
    for side, items in placed.items():
        sgn = 1 if side == "R" else -1
        for p, s, mid, y in items:
            x0, y0 = np.cos(mid) * 1.0, np.sin(mid) * 1.0
            xl = sgn * max(abs(np.cos(mid)) * 1.12, 1.08)
            ax.plot([x0, xl, xl + sgn * 0.08], [y0, y, y], color="#A6A6A6", lw=0.7, zorder=2)
            strong = cmap[p] in (M["navy"], M["sky"])
            ax.text(xl + sgn * 0.11, y, f"{p} {vf(s)}", ha="left" if side == "R" else "right",
                    va="center", fontsize=9.2, color=M["navy"] if strong else M["ink"],
                    fontweight="bold" if strong else "normal", zorder=5)


def donuts(rings, title=None, source=None, unit=None, number=None, highlight=None, value_fmt="%",
           notes=None, notes_title=None, out=None, figsize=None):
    """One or more rings side by side; the same part keeps the same colour in every ring.

    rings: [{"subtitle": "收入", "parts": ["商品销售", "服务收入"], "values": [85, 15],
             "center": "收入\\n100%"}, …]   highlight: part name(s), two at most."""
    _check_cjk(title, source, *[r.get("subtitle", "") + "".join(r["parts"]) for r in rings])
    k = len(rings)
    allparts = []
    for r in rings:
        allparts += [p for p in r["parts"] if p not in allparts]
    cmap = _donut_colors(allparts, highlight)
    figsize = figsize or (3.9 * k + 0.6, 4.4)
    figsize, side = _prep_notes(notes, figsize)
    fig, ax0 = _frame_mono(figsize, _numbered(title, number), source, unit, side=side)
    floor, ceil = ax0._ic_bounds
    right = (0.04 + 0.92 * (1 - side) - 0.01) if side else 0.96
    if side:
        ax0_side = ax0._ic_side
    ax0.remove()
    w = (right - 0.04) / k
    for i, r in enumerate(rings):
        ax = fig.add_axes([0.04 + i * w, floor + 0.01, w, ceil - floor - 0.03])
        _draw_donut(ax, r["parts"], r["values"], center=r.get("center"), value_fmt=value_fmt,
                    colors=cmap, subtitle=r.get("subtitle"))
        if notes and i == 0:
            ax._ic_side = ax0_side
            holder = ax
    if notes:
        _side_notes(fig, holder, notes, notes_title)
    return _save(fig, out)


# --------------------------------------------------------------------------
# Recipe 16 — stacked components with a total line, one or two companies side by side
# --------------------------------------------------------------------------
def _draw_stacked_total(ax, x, groups, yfmt=None, total_fmt=None, labels=None, colors=None,
                        marks=None, legend=True):
    M = MONO
    x = list(x)
    n = len(x)
    g = len(groups)
    bases = colors or [M["navy"], M["salmon"], "#7F7F7F"]
    width = 0.74 / g
    tf = fmt(total_fmt or yfmt)
    labels = labels if labels is not None else ("all" if g == 1 else "ends")
    entries = []
    totals_all = {}
    for gi, (gname, layers) in enumerate(groups.items()):
        names = list(layers)
        shades = ramp(bases[gi % len(bases)], len(names) + 1)[:len(names)]
        off = (gi - (g - 1) / 2) * width
        bottom = np.zeros(n)
        for li, name in enumerate(names):
            v = np.nan_to_num(np.array(layers[name], dtype=float))
            ax.bar(np.arange(n) + off, v, bottom=bottom, width=width * 0.92, color=shades[li],
                   edgecolor="white", lw=0.5, zorder=3)
            bottom += v
        totals_all[gname] = bottom
        c = bases[gi % len(bases)]
        ax.plot(np.arange(n) + off, bottom, color=c, lw=1.6, marker="o", ms=3.6, zorder=5)
        pick = range(n) if labels == "all" else ([0, n - 1] if labels == "ends" else [])
        for i in pick:
            ax.annotate(tf(bottom[i]), (i + off, bottom[i]), xytext=(0, 6), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8.8, fontweight="bold", color=c, zorder=7,
                        path_effects=[pe.withStroke(linewidth=2.4, foreground="white")])
        entries.append([(Line2D([0], [0], color=c, lw=1.6, marker="o", ms=3.6), f"{gname}合计"
                         if _CJK.search(str(gname)) else f"{gname} total")] +
                       [(Patch(facecolor=shades[li]), nm) for li, nm in enumerate(names)])
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_xticks(range(n))
    ax.set_xticklabels(x, fontsize=9.5, color=M["tick"])
    top = max(t.max() for t in totals_all.values())
    ax.set_ylim(0, top * 1.16)
    ax.yaxis.set_major_locator(MaxNLocator(7, steps=[1, 2, 2.5, 5, 10]))
    ax.yaxis.set_major_formatter(_tickfmt(yfmt))
    if legend:
        cols = max(len(e) for e in entries)
        hs, ns = [], []
        for col in range(cols):                       # column-major fill → one row per company
            for e in entries:
                h, nm = e[col] if col < len(e) else (Patch(alpha=0), "")
                hs.append(h)
                ns.append(nm)
        ax.legend(hs, ns, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=cols, frameon=False,
                  fontsize=9, handlelength=1.4, columnspacing=1.2, handletextpad=0.5)
    _draw_marks(ax, x, marks, totals_all)


def stacked_total(x, groups, title=None, source=None, unit=None, number=None, yfmt=None,
                  total_fmt=None, labels=None, colors=None, marks=None, notes=None, notes_title=None,
                  out=None, figsize=(8.0, 4.9)):
    """Components stacked into a total, the total drawn as a line through the bar tops; two
    companies side by side in navy and salmon shades.

    groups: {"A 公司": {"研发": [...], "折旧": [...]}, "B 公司": {...}}  layers bottom → top.
    labels: "all" (default with one company), "ends" (default with two), or null."""
    _check_cjk(title, source, unit, *groups, *x)
    figsize, side = _prep_notes(notes, figsize)
    fig, ax = _frame_mono(figsize, _numbered(title, number), source, unit, side=side)
    _draw_stacked_total(ax, x, groups, yfmt, total_fmt, labels, colors, marks)
    _fit(ax)
    if notes:
        _side_notes(fig, ax, notes, notes_title)
    return _save(fig, out)


def _panel_donut(ax, parts, values, highlight=None, center=None, value_fmt="%"):
    _draw_donut(ax, parts, values, highlight=highlight, center=center, value_fmt=value_fmt)


_PANEL_DRAWERS.update(waterfall=_draw_waterfall, aligned=_draw_aligned, donut=_panel_donut,
                      stacked_total=_draw_stacked_total)


# --------------------------------------------------------------------------
# JSON front door
# --------------------------------------------------------------------------
RECIPES = {
    "trend_events": trend_events,
    "stacked_family": stacked_family,
    "bar_line": bar_line,
    "panel_grid": panel_grid,
    "area_highlight": area_highlight,
    "scenario_fan": scenario_fan,
    "capability_ladder": capability_ladder,
    "phase_trend": phase_trend,
    "waterfall": waterfall,
    "aligned_compare": aligned_compare,
    "process_cost": process_cost,
    "share_compare": share_compare,
    "flywheel": flywheel,
    "tiers": tiers,
    "donuts": donuts,
    "stacked_total": stacked_total,
}


def render(spec, out=None):
    """Render one chart from a dict: {"recipe": name, ...arguments}."""
    spec = dict(spec)
    name = spec.pop("recipe")
    if name not in RECIPES:
        raise SystemExit(f"unknown recipe {name!r}; choose from {', '.join(RECIPES)}")
    out = out or spec.pop("out", None) or f"{name}.png"
    spec.pop("out", None)
    fn = RECIPES[name]
    params = inspect.signature(fn).parameters
    if not any(p.kind is p.VAR_KEYWORD for p in params.values()):
        bad = [k for k in spec if k not in params]
        if bad:
            raise SystemExit(f"{name}: unknown key(s) {', '.join(map(repr, bad))}. "
                             f"Valid keys: {', '.join(k for k in params if k != 'out')}")
    try:
        fig = fn(out=out, **spec)
    except TypeError as e:
        raise SystemExit(f"{name}: {e}. See references/recipes.md for the parameter table.") from None
    plt.close(fig)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render an insight-charts JSON spec to an image.")
    ap.add_argument("spec", nargs="?", help="path to a JSON spec, or - for stdin")
    ap.add_argument("-o", "--out", help="output file (.png, .svg or .pdf)")
    ap.add_argument("--list", action="store_true", help="list recipes and icons")
    ap.add_argument("--fonts", action="store_true", help="show which fonts will be used")
    a = ap.parse_args(argv)
    if a.list:
        print("recipes:", ", ".join(RECIPES))
        print("icons:  ", ", ".join(ICONS))
        return 0
    if a.fonts:
        cjk = setup_fonts()
        print("font chain:", plt.rcParams["font.family"])
        print("Chinese text:", "ok" if cjk else "NO CJK FONT — install Noto Sans SC")
        return 0
    if not a.spec:
        ap.error("spec is required")
    raw = sys.stdin.read() if a.spec == "-" else open(a.spec, encoding="utf-8").read()
    print(render(json.loads(raw), a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
