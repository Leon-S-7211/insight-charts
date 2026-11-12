#!/usr/bin/env python3
"""insight_charts — research-grade chart recipes on top of matplotlib.

Two themes, six recipes. Import it, or drive it with a JSON spec:

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
from matplotlib.patches import Circle, FancyBboxPatch, Patch, Polygon, Rectangle  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

__version__ = "0.1.0"

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


def _frame_teal(figsize=(10, 7.2), title=None, brand=None, plot_rect=None, source=None, unit=None):
    setup_fonts()
    T = TEAL
    fig = plt.figure(figsize=figsize, facecolor="white")
    wide = figsize[0] / 10
    tl = _wrap(title, int(46 * wide))
    top = 0.90 if not tl else (0.815 if len(tl) == 1 else 0.765)
    if unit:
        top -= 0.03
    bottom = 0.30 if not source else 0.315
    rect = plot_rect or [0.125, bottom, 0.80, top - bottom]
    ax = fig.add_axes(rect)
    if tl:
        fig.text(0.075, 0.955, "\n".join(tl), fontsize=23 if len(tl) == 1 else 20,
                 fontweight="bold", color=T["ink"], ha="left", va="top", linespacing=1.18)
    if unit:
        fig.text(rect[0] - 0.05, top + 0.022, unit, fontsize=11, fontweight="bold",
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


def _frame_mono(figsize=(7.2, 4.9), title=None, source=None, unit=None, fig=None, cell=None):
    """Sell-side frame: bold conclusion title, hairline, plot, hairline, source.

    cell = (left, bottom, width, height) in figure fractions lets several frames share a figure.
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
    ax = fig.add_axes([L + 0.085 * W, B + src_h + pad_b, W * 0.83,
                       H - title_h - src_h - unit_h - pad_t - pad_b])
    ax._ic_bounds = (B + src_h + 7 * pt, y - title_h - unit_h - 7 * pt)
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
                 source=None, unit=None, brand=None, out=None, figsize=(10, 7.2)):
    """Multi-line trend with vertical event dividers (model launches, policy dates, price moves).

    x: list of category labels (dates as strings). series: {name: values}.
    events: [{"at": label-or-index, "label": "Opus 4.5\\nClaude Cowork"}].
    chip: "soft" grey chips for context events, "ink" dark chips when the events ARE the story."""
    T = TEAL
    _check_cjk(title, ylabel, source, unit, *series)
    fig, ax = _frame_teal(figsize, title, brand, source=source, unit=unit)
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
                   brand=None, out=None, figsize=(10, 7.2)):
    """Stacked bars where colour encodes family first, generation second.

    layers: {member: values} in bottom-to-top order.
    families: {"Sonnet": ["Sonnet 5.5", "Sonnet 5", ...], "Opus": [...]} newest first.
    minor: small leftovers that get accent colours and sit on top."""
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
                   left_ylim=None, legend="top", note=None):
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
             ylabel=None, right_label=None, out=None, figsize=None, brand=None, **kw):
    """Level as bars, ratio as a line. theme="mono" → grey bars, labelled; "teal" → pale bars."""
    _check_cjk(title, source, unit)
    if _theme(theme)["name"] == "mono":
        fig, ax = _frame_mono(figsize or (7.2, 4.9), _numbered(title, number), source, unit)
        _fit(ax, _draw_bar_line(ax, x, bars, line, "mono", **kw))
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
               left_fmt=None, hide_y=False):
    M = MONO
    if left_fmt is None and value_fmt in ("%", "%1", "$", "$2"):
        left_fmt = value_fmt[0]              # the axis speaks the same unit as the labels
    _draw_bar_line(ax, x, values, None, "mono", bar_fmt=value_fmt, left_fmt=left_fmt,
                   highlight=highlight, forecast_from=forecast_from, legend=None, note=note)
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

    {"kind": "bar_line" | "cost_steps" | "bars" | "area" | "lines",
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
               theme="mono"):
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


def area_highlight(x, layers, highlight=None, annotation=None, title=None, source=None, unit=None,
                   number=None, yfmt=None, xtick_every=None, out=None, figsize=(7.4, 5.0)):
    """Stacked area: the layer that carries the story is tinted, the rest step down in grey.

    annotation: {"at": x-label-or-index, "text": "Announced 30%\\nprice hike", "y": 0}"""
    _check_cjk(title, source, unit, *layers)
    fig, ax = _frame_mono(figsize, _numbered(title, number), source, unit)
    _draw_area(ax, x, layers, highlight, annotation, yfmt, xtick_every)
    _fit(ax)
    return _save(fig, out)


def _draw_lines(ax, x, series, yfmt=None, colors=None, end_labels=True, xtick_every=None,
                steps=False, ylim=None):
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
