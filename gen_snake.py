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
STEP = 0.12           # seconds per cell (was 0.10 -> a little slower)
DENSE = 0.35          # >= this share of green days -> full sweep path; below -> short walks
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


def demo_weeks(kind="mid"):
    random.seed(7)
    pool = {"sparse": [0] * 60 + [1, 2, 3, 4], "mid": [0] * 8 + [1, 2, 3, 4],
            "dense": [0, 1, 2, 3, 4, 4]}[kind]
    return [[(d, random.choice(pool)) for d in range(7)] for _ in range(53)]


def seg_size(i):
    """snk sizing: head = 0.9*cell, shrinking over the first 4 segments down to
    0.8*dot. Every segment after that (the ones gained by eating) keeps that
    smallest size."""
    d_min, d_max = SIZE_DOT * 0.8, SIZE_CELL * 0.9
    u = (1 - min(i, 4) / 4) ** 2
    return (1 - u) * d_min + u * d_max


def plan_route(grid, ncols):
    """Pick the snake's path.

    * dense graph  -> boustrophedon sweep over every cell (smooth, regular)
    * sparse graph -> nearest-green-first walk: from where the head is, take the
      SHORTEST path (BFS, staying inside the grid and not running into its own
      body) to the closest remaining green cell. Far fewer steps, so the
      animation is shorter and smoother.
    """
    zig = [(c, r) for c in range(ncols)
           for r in (range(7) if c % 2 == 0 else range(6, -1, -1))]
    food = {p for p, lvl in grid.items() if lvl > 0}
    if not food or len(food) / max(len(grid), 1) >= DENSE:
        return zig

    start = (0, 0) if (0, 0) in grid else min(grid)
    route = [start]
    remaining = set(food) - {start}
    length = START_LEN

    def neighbours(c, r):
        for dc, dr in ((1, 0), (0, 1), (0, -1), (-1, 0)):   # prefer moving right
            n = (c + dc, r + dr)
            if n in grid:
                yield n

    def bfs(avoid_body):
        head = route[-1]
        parent = {head: None}
        frontier = [head]
        depth = 0
        while frontier:
            depth += 1
            # cells still occupied by the body after `depth` steps
            keep = length - depth
            blocked = set(route[len(route) - keep:]) if (avoid_body and keep > 0) else set()
            nxt = []
            for cell in frontier:
                for n in neighbours(*cell):
                    if n in parent or n in blocked:
                        continue
                    parent[n] = cell
                    nxt.append(n)
            hits = [n for n in nxt if n in remaining]
            if hits:
                goal = min(hits)            # tie -> leftmost column first (no stranded cells)
                path = []
                while goal != head:
                    path.append(goal)
                    goal = parent[goal]
                return path[::-1]
            frontier = nxt
        return None

    while remaining:
        path = bfs(True) or bfs(False)
        if not path:
            break
        for cell in path:
            route.append(cell)
            if cell in remaining:
                remaining.discard(cell)
                length += 1
    if remaining:
        return zig
    # if the short walk keeps running into its own body, the regular sweep looks cleaner
    L, eaten, hits = START_LEN, set(), 0
    for i, p in enumerate(route):
        if i > 0 and p in route[max(0, i - L):i]:
            hits += 1
        if i > 0 and p in food and p not in eaten:
            eaten.add(p)
            L += 1
    return route if hits <= 0.02 * len(route) else zig


def build(weeks):
    ncols = len(weeks)
    grid = {(c, r): lvl for c, w in enumerate(weeks) for r, lvl in w}

    route = plan_route(grid, ncols)
    n = len(route)
    pts = [(SIZE_CELL + c * SIZE_CELL + SIZE_CELL / 2,
            SIZE_CELL + r * SIZE_CELL + SIZE_CELL / 2) for c, r in route]

    # first time the head reaches each green cell = when it is eaten
    first = {}
    for i, p in enumerate(route):
        if p not in first:
            first[p] = i
    eats = sorted(i for p, i in first.items() if grid.get(p, 0) > 0 and i > 0)
    max_len = START_LEN + len(eats)

    total_steps = n + max_len + HOLD
    T = total_steps * STEP

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
    h = (n - 1) * STEP / T if n > 1 else 0.0

    out = {}
    for fname, th in THEMES.items():
        p = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
             f'viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
             f'role="img" aria-label="Contribution snake">',
             f'<defs><path id="route" d="{d_path}"/></defs>']

        # cells (every day of the graph)
        for (c, r), lvl in sorted(grid.items()):
            x = SIZE_CELL + c * SIZE_CELL + (SIZE_CELL - SIZE_DOT) / 2
            y = SIZE_CELL + r * SIZE_CELL + (SIZE_CELL - SIZE_DOT) / 2
            idx = first.get((c, r))
            if lvl > 0 and idx == 0:
                lvl = 0                       # eaten right at the start
            col = th["dots"][lvl]
            base = (f'<rect x="{x:g}" y="{y:g}" width="{SIZE_DOT}" height="{SIZE_DOT}" '
                    f'rx="{RADIUS}" ry="{RADIUS}" fill="{col}" stroke="{th["border"]}" stroke-width="1"')
            if lvl > 0 and idx is not None:
                a = idx * STEP / T
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
    demo = next((a for a in sys.argv if a.startswith("--demo")), None)
    weeks = demo_weeks(demo.split("=")[1] if demo and "=" in demo else "mid") if demo else fetch_weeks()
    os.makedirs(OUT, exist_ok=True)
    for name, svg in build(weeks).items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", os.path.join(OUT, name), f"({len(svg) // 1024} KB)")
