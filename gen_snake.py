#!/usr/bin/env python3
"""
Contribution snake in the classic Platane/snk look (purple rounded-square
snake, GitHub palettes) with ONE change: every time it eats a contribution
cell, the snake grows by exactly one segment.

Outputs dist/github-snake.svg (light) and dist/github-snake-dark.svg (dark).
Pure SMIL animation, no JavaScript.

  GH_TOKEN=... python gen_snake.py     # real data (private contributions are
                                       # included if the token/profile allow it)
  python gen_snake.py --demo           # fake data, for testing
"""
import json
import os
import random
import sys
import urllib.request

USER = os.environ.get("GH_USER", "RicksonLivio")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT = os.environ.get("OUT_DIR", "dist")

# --- snk defaults -----------------------------------------------------------
SIZE_CELL = 16        # grid pitch
SIZE_DOT = 12         # cell size
RADIUS = 2            # cell / segment corner radius
SNAKE_COLOR = "purple"    # snk default snake colour
START_LEN = 4         # snk starts with 4 segments
STEP = 0.1            # seconds per cell
HOLD = 12             # extra steps of rest at the end of the loop

THEMES = {
    "github-snake.svg": dict(          # GitHub light contribution colours
        border="#1b1f230a",
        dots=["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]),
    "github-snake-dark.svg": dict(     # GitHub dark contribution colours
        border="#1b1f230a",
        dots=["#151b23", "#033a16", "#196c2e", "#2ea043", "#56d364"]),
}

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

QUERY = """query($login:String!){user(login:$login){contributionsCollection{
contributionCalendar{weeks{contributionDays{contributionLevel weekday}}}}}}"""


def fetch_weeks():
    if not TOKEN:
        sys.exit("Set GH_TOKEN (or GITHUB_TOKEN).")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}",
                 "Content-Type": "application/json",
                 "User-Agent": "growing-snake"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(str(data["errors"]))
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [[(d["weekday"], LEVELS[d["contributionLevel"]]) for d in w["contributionDays"]]
            for w in weeks]


def demo_weeks():
    random.seed(7)
    return [[(d, random.choice([0, 0, 0, 0, 0, 1, 2, 3])) for d in range(7)] for _ in range(53)]


def seg_size(i):
    """snk sizing: head = 0.9*cell, shrinking over the first 4 segments down to
    0.8*dot. Every segment after that (the ones gained by eating) keeps that
    smallest size."""
    d_min, d_max = SIZE_DOT * 0.8, SIZE_CELL * 0.9
    u = (1 - min(i, 4) / 4) ** 2
    return (1 - u) * d_min + u * d_max


def build(weeks):
    ncols = len(weeks)
    grid = {(c, r): lvl for c, w in enumerate(weeks) for r, lvl in w}

    # zig-zag over EVERY cell of the 53x7 grid (missing days are padded and
    # not drawn) so every step has the same length -> constant speed.
    route = []
    for c in range(ncols):
        rows = range(7) if c % 2 == 0 else range(6, -1, -1)
        for r in rows:
            route.append((c, r))
    n = len(route)
    level = [grid.get(p, 0) for p in route]
    drawn = [p in grid for p in route]

    off = SIZE_CELL + (SIZE_CELL - SIZE_DOT) / 2          # 1-cell margin, centred dot
    def center(c, r):
        return (SIZE_CELL + c * SIZE_CELL + SIZE_CELL / 2,
                SIZE_CELL + r * SIZE_CELL + SIZE_CELL / 2)
    pts = [center(c, r) for c, r in route]

    # eating events: head arrives at route index e at time e*STEP
    eats = [i for i in range(1, n) if level[i] > 0 and drawn[i]]
    max_len = START_LEN + len(eats)

    total_steps = n + max_len + HOLD
    T = total_steps * STEP

    # segment k: appears when snake length > k and its index is on the grid
    appear = []
    for k in range(max_len):
        if k < START_LEN:
            a = k * STEP
        else:
            a = max(eats[k - START_LEN] * STEP, k * STEP)
        appear.append(a)
    vanish = [(n - 1 + k + 0.5) * STEP for k in range(max_len)]

    width = (ncols + 2) * SIZE_CELL
    height = (7 + 2) * SIZE_CELL
    d_path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    h = (n - 1) * STEP / T

    out = {}
    for fname, th in THEMES.items():
        p = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
             f'viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
             f'role="img" aria-label="Contribution snake">',
             f'<defs><path id="route" d="{d_path}"/></defs>']

        # cells
        for i, (c, r) in enumerate(route):
            if not drawn[i]:
                continue
            x = SIZE_CELL + c * SIZE_CELL + (SIZE_CELL - SIZE_DOT) / 2
            y = SIZE_CELL + r * SIZE_CELL + (SIZE_CELL - SIZE_DOT) / 2
            col = th["dots"][level[i]]
            base = (f'<rect x="{x:g}" y="{y:g}" width="{SIZE_DOT}" height="{SIZE_DOT}" '
                    f'rx="{RADIUS}" ry="{RADIUS}" fill="{col}" stroke="{th["border"]}" stroke-width="1"')
            if level[i] > 0:
                a = i * STEP / T
                p.append(base + '>'
                         f'<animate attributeName="fill" values="{col};{th["dots"][0]}" '
                         f'keyTimes="0;{a:.5f}" calcMode="discrete" dur="{T:.2f}s" '
                         f'repeatCount="indefinite"/></rect>')
            else:
                p.append(base + '/>')

        # snake: tail first so the head is drawn on top
        for k in reversed(range(max_len)):
            size = seg_size(k)
            half = size / 2
            rad = min(4.5, 4 * size / SIZE_DOT)
            a = appear[k] / T
            b = vanish[k] / T
            p.append(
                f'<rect x="{-half:.2f}" y="{-half:.2f}" width="{size:.2f}" height="{size:.2f}" '
                f'rx="{rad:.2f}" ry="{rad:.2f}" fill="{SNAKE_COLOR}" opacity="0">'
                f'<animateMotion dur="{T:.2f}s" begin="{k * STEP:.2f}s" repeatCount="indefinite" '
                f'keyPoints="0;1;1" keyTimes="0;{h:.5f};1" calcMode="linear">'
                f'<mpath xlink:href="#route"/></animateMotion>'
                f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;{a:.5f};{b:.5f}" '
                f'calcMode="discrete" dur="{T:.2f}s" repeatCount="indefinite"/></rect>')
        p.append("</svg>")
        out[fname] = "\n".join(p)
    return out


if __name__ == "__main__":
    weeks = demo_weeks() if "--demo" in sys.argv else fetch_weeks()
    os.makedirs(OUT, exist_ok=True)
    for name, svg in build(weeks).items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", os.path.join(OUT, name), f"({len(svg) // 1024} KB)")
