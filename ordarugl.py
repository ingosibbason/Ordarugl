#!/usr/bin/env python3
"""Orðarugl — Icelandic word search generator."""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


# Full Icelandic uppercase alphabet (32 letters).
ALPHABET = list("AÁBDÐEÉFGHIÍJKLMNOÓPRSTUÚVXYÝÞÆÖ")
ALPHABET_SET = set(ALPHABET)
ALPHABET_ORDER = {ch: i for i, ch in enumerate(ALPHABET)}


def icelandic_sort_key(word: str) -> tuple[int, ...]:
    """Sort key that matches the Icelandic alphabet (Þ, Æ, Ö after Y/Ý)."""
    return tuple(ALPHABET_ORDER.get(c, len(ALPHABET)) for c in word.upper())

# 8 directions as (dr, dc).
DIR_E  = (0, 1)
DIR_S  = (1, 0)
DIR_SE = (1, 1)
DIR_W  = (0, -1)
DIR_N  = (-1, 0)
DIR_NW = (-1, -1)
DIR_NE = (-1, 1)
DIR_SW = (1, -1)

ALL_DIRS = [DIR_E, DIR_S, DIR_SE, DIR_W, DIR_N, DIR_NW, DIR_NE, DIR_SW]
DIAGONALS = {DIR_SE, DIR_NW, DIR_NE, DIR_SW}
# "Forward" = word reads naturally left-to-right and/or top-to-bottom.
FORWARD = {DIR_E, DIR_S, DIR_SE}


def resolve_directions(no_diagonals: bool, no_backwards: bool) -> list[tuple[int, int]]:
    dirs = set(ALL_DIRS)
    if no_diagonals:
        dirs -= DIAGONALS
    if no_backwards:
        dirs &= FORWARD
    return sorted(dirs)


def normalize_word(word: str) -> str:
    """Uppercase and validate against the Icelandic alphabet."""
    upper = word.strip().upper()
    if not upper:
        raise ValueError("empty word")
    bad = sorted({c for c in upper if c not in ALPHABET_SET})
    if bad:
        raise ValueError(
            f"word {word!r} contains characters not in the Icelandic alphabet: {''.join(bad)}"
        )
    return upper


def try_place(grid, word, directions, rng, max_attempts=300):
    rows, cols = len(grid), len(grid[0])
    n = len(word)
    for _ in range(max_attempts):
        dr, dc = rng.choice(directions)
        if dr > 0:
            r_lo, r_hi = 0, rows - n
        elif dr < 0:
            r_lo, r_hi = n - 1, rows - 1
        else:
            r_lo, r_hi = 0, rows - 1
        if dc > 0:
            c_lo, c_hi = 0, cols - n
        elif dc < 0:
            c_lo, c_hi = n - 1, cols - 1
        else:
            c_lo, c_hi = 0, cols - 1
        if r_lo > r_hi or c_lo > c_hi:
            continue
        r = rng.randint(r_lo, r_hi)
        c = rng.randint(c_lo, c_hi)
        cells = [(r + dr * i, c + dc * i) for i in range(n)]
        if all(grid[pr][pc] in (None, word[i]) for i, (pr, pc) in enumerate(cells)):
            for i, (pr, pc) in enumerate(cells):
                grid[pr][pc] = word[i]
            return cells
    return None


def build_puzzle(words, n, directions, rng, grow=True, max_grows=20):
    """Place words on a square n×n grid, optionally growing until everything fits."""
    words = sorted(words, key=len, reverse=True)
    for _ in range(max_grows if grow else 1):
        grid = [[None] * n for _ in range(n)]
        placements: dict[str, list[tuple[int, int]]] = {}
        dropped: list[str] = []
        for word in words:
            pos = try_place(grid, word, directions, rng)
            if pos is None:
                dropped.append(word)
            else:
                placements[word] = pos
        if not dropped:
            return grid, placements, [], n
        if not grow:
            return grid, placements, dropped, n
        n += 1
    return grid, placements, dropped, n


def fill_grid(grid, letters_pool, rng):
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] is None:
                grid[r][c] = rng.choice(letters_pool)


# ---------- PDF rendering ----------

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm
TITLE_BLUE = HexColor("#2E73B8")
HIGHLIGHT = HexColor("#FFD93D")

LIST_COLS = 4
LIST_FONT_MAX = 18  # pt — cap so very small lists don't get absurd
LIST_FONT_MIN = 8
LIST_LINE_RATIO = 1.55  # line height as multiple of font size


def render_pdf(out_path, title, grid, word_list, placements=None, highlight=False):
    n = len(grid)  # grid is square
    c = canvas.Canvas(str(out_path), pagesize=A4)

    # Title bar (top-left blue strip).
    title_h = 14 * mm
    c.setFont("Helvetica-Bold", 20)
    title_w = max(80 * mm, c.stringWidth(title, "Helvetica-Bold", 20) + 18 * mm)
    title_y = PAGE_H - MARGIN - title_h
    c.setFillColor(TITLE_BLUE)
    c.rect(MARGIN, title_y, title_w, title_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.drawString(MARGIN + 6 * mm, title_y + 4.6 * mm, title)

    # --- Layout: maximize both the square grid and the word-list font size ---
    border_pad = 4 * mm
    gap_after_title = 8 * mm
    gap_before_list = 10 * mm

    avail_w_grid = PAGE_W - 2 * MARGIN - 2 * border_pad
    cell_from_width = avail_w_grid / n

    # Word list sizing: 4 columns. Font is the largest that lets the widest
    # displayed word fit its column comfortably.
    list_col_w = (PAGE_W - 2 * MARGIN) / LIST_COLS
    displayed = [w[0] + w[1:].lower() if len(w) > 1 else w for w in word_list]
    longest_display = max((len(d) for d in displayed), default=1)
    # Helvetica avg char width ≈ 0.55 × font size; leave ~10% padding in column.
    font_from_width = (list_col_w * 0.90) / (longest_display * 0.55)
    list_font = min(LIST_FONT_MAX, font_from_width)
    list_line_h = list_font * LIST_LINE_RATIO
    list_rows = math.ceil(len(word_list) / LIST_COLS) if word_list else 0
    list_h = list_rows * list_line_h

    # Total vertical between title and bottom margin, minus fixed gaps and pads.
    total_v = title_y - MARGIN - gap_after_title - 2 * border_pad - gap_before_list
    avail_h_grid = total_v - list_h
    cell_from_height = avail_h_grid / n

    cell = min(cell_from_width, cell_from_height)

    # If the grid was width-constrained, donate the leftover vertical space
    # to the word-list font (until it hits the per-column width cap).
    leftover_v = avail_h_grid - cell * n
    if leftover_v > 0 and list_rows > 0:
        max_list_h = list_h + leftover_v
        font_from_height = (max_list_h / list_rows) / LIST_LINE_RATIO
        list_font = min(LIST_FONT_MAX, font_from_width, font_from_height)
        list_line_h = list_font * LIST_LINE_RATIO

    if list_font < LIST_FONT_MIN:
        list_font = LIST_FONT_MIN
        list_line_h = list_font * LIST_LINE_RATIO

    grid_side = cell * n
    grid_x = (PAGE_W - grid_side) / 2
    grid_y = title_y - gap_after_title - border_pad - grid_side

    # Distribute any unused vertical (grid was width-constrained) by pushing
    # the word list down so it sits closer to the bottom margin.
    used_v = grid_side + list_h
    extra_v = max(0.0, total_v - used_v)
    list_gap = gap_before_list + extra_v

    # Dotted border around the grid.
    c.setStrokeColor(black)
    c.setLineWidth(0.9)
    c.setDash(1, 3)
    c.rect(
        grid_x - border_pad,
        grid_y - border_pad,
        grid_side + 2 * border_pad,
        grid_side + 2 * border_pad,
        fill=0,
        stroke=1,
    )
    c.setDash()

    def cell_center(r, ci):
        x = grid_x + ci * cell + cell / 2
        # PDF origin bottom-left; row 0 is top of grid.
        y = grid_y + (n - r - 0.5) * cell
        return x, y

    # Solution highlights (drawn under the letters).
    if highlight and placements:
        c.setStrokeColor(HIGHLIGHT)
        c.setLineCap(1)
        c.setLineWidth(cell * 0.72)
        for positions in placements.values():
            x0, y0 = cell_center(*positions[0])
            x1, y1 = cell_center(*positions[-1])
            c.line(x0, y0, x1, y1)

    # Letters.
    c.setFillColor(black)
    letter_font = cell * 0.58
    c.setFont("Helvetica-Bold", letter_font)
    y_adjust = letter_font * 0.32
    for r in range(n):
        for ci in range(n):
            x, y = cell_center(r, ci)
            c.drawCentredString(x, y - y_adjust, grid[r][ci])

    # Word list — 4 columns, column-major, dynamic font size.
    if word_list:
        per_col = math.ceil(len(word_list) / LIST_COLS)
        # Baseline of the first (top) row of the list.
        first_baseline = grid_y - border_pad - list_gap - list_font * 0.85
        c.setFont("Helvetica", list_font)
        c.setFillColor(black)
        for i, display in enumerate(displayed):
            col_idx = i // per_col
            row_idx = i % per_col
            x = MARGIN + col_idx * list_col_w
            y = first_baseline - row_idx * list_line_h
            c.drawString(x, y, display)

    c.showPage()
    c.save()


# ---------- CLI ----------

def parse_words(args) -> list[str]:
    if args.words:
        raw = [w for w in args.words.split(",") if w.strip()]
    else:
        path = Path(args.words_file)
        if not path.exists():
            sys.exit(f"words file not found: {path}")
        raw = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                raw.append(line)
    if not raw:
        sys.exit("no words supplied")
    try:
        return [normalize_word(w) for w in raw]
    except ValueError as e:
        sys.exit(str(e))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="ordarugl",
        description="Generate an Icelandic word search puzzle as a printable PDF.",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--words", help="comma-separated list of words")
    src.add_argument("--words-file", help="path to a file with one word per line")
    p.add_argument("--size", type=int, help="grid side length (default: auto-fit). Grid is always square.")
    # --cols / --rows kept for compatibility — both now mean the side length.
    p.add_argument("--cols", type=int, help=argparse.SUPPRESS)
    p.add_argument("--rows", type=int, help=argparse.SUPPRESS)
    p.add_argument("--title", default="Orðarugl", help='title text (default: "Orðarugl")')
    p.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard"],
        default="medium",
        help="preset: easy = horizontal/vertical only; medium = + diagonals; hard = all 8 directions",
    )
    p.add_argument("--no-diagonals", action="store_true", help="disallow diagonal placement")
    p.add_argument("--no-backwards", action="store_true", help="disallow backwards placement")
    p.add_argument("--out", default="puzzle.pdf", help="output PDF path (solution: <out>-solution.pdf)")
    p.add_argument("--seed", type=int, help="random seed for reproducible puzzles")

    args = p.parse_args(argv)
    words = parse_words(args)

    # Difficulty preset combined with explicit flags (more restrictive wins).
    no_diag = args.no_diagonals or args.difficulty == "easy"
    no_back = args.no_backwards or args.difficulty in ("easy", "medium")
    directions = resolve_directions(no_diag, no_back)
    if not directions:
        sys.exit("no directions enabled — relax the difficulty flags")

    rng = random.Random(args.seed)

    longest = max(len(w) for w in words)
    total_letters = sum(len(w) for w in words)
    default_n = max(longest, math.ceil(math.sqrt(total_letters * 1.8)), 12)

    user_sizes = [s for s in (args.size, args.cols, args.rows) if s is not None]
    if user_sizes:
        n = max(user_sizes)
        if len(set(user_sizes)) > 1:
            print(
                f"Note: grid is square — using {n} (the largest of the supplied sizes).",
                file=sys.stderr,
            )
        user_fixed = True
    else:
        n = default_n
        user_fixed = False

    if longest > n:
        sys.exit(f"longest word ({longest} letters) doesn't fit in a {n}x{n} grid")

    grid, placements, dropped, final_n = build_puzzle(
        words, n, directions, rng, grow=not user_fixed
    )
    if final_n != n:
        print(
            f"Grew grid from {n}x{n} to {final_n}x{final_n} to fit all words.",
            file=sys.stderr,
        )
    if dropped:
        print(
            f"Warning: could not place {len(dropped)} word(s): {', '.join(dropped)}",
            file=sys.stderr,
        )

    # Filler alphabet: only letters that already appear in input words (spec).
    used_letters = sorted({ch for w in words for ch in w})
    fill_grid(grid, used_letters, rng)

    out_path = Path(args.out)
    sol_path = out_path.with_name(out_path.stem + "-solution" + out_path.suffix)

    sorted_words = sorted(words, key=icelandic_sort_key)
    placed_sorted = [w for w in sorted_words if w in placements]
    render_pdf(out_path, args.title, grid, sorted_words, placements=placements, highlight=False)
    render_pdf(
        sol_path,
        f"{args.title} — Lausn",
        grid,
        placed_sorted,
        placements=placements,
        highlight=True,
    )

    print(f"Wrote {out_path}")
    print(f"Wrote {sol_path}")
    return 1 if dropped else 0


if __name__ == "__main__":
    sys.exit(main())
