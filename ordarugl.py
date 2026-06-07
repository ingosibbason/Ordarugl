#!/usr/bin/env python3
"""Orðarugl — Icelandic word search generator."""

from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import NamedTuple

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


class OrdaruglInputError(ValueError):
    """User-input error suitable for showing to an end user.

    Subclasses ValueError so existing callers that catch ValueError keep working.
    """


# Full Icelandic uppercase alphabet (32 letters), plus (C,Q,W,Z) (36 letters)
ALPHABET = list("AÁBCDÐEÉFGHIÍJKLMNOÓPQRSTUÚVWXYÝZÞÆÖ") 
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


class Word(NamedTuple):
    display: str    # what the user typed (preserved for the word list)
    placement: str  # uppercase, no spaces/dashes (used to place in the grid)


# Characters allowed inside user input but stripped before placement.
_SEPARATORS = set(" \t -–—")


def normalize_word(raw: str) -> Word:
    """Return display + placement forms of a user-supplied word."""
    display = " ".join(raw.split())  # trim + collapse internal whitespace
    if not display:
        raise OrdaruglInputError("empty word")
    placement = "".join(c for c in display.upper() if c not in _SEPARATORS)
    if not placement:
        raise OrdaruglInputError(f"word {raw!r} has no letters")
    bad = sorted({c for c in placement if c not in ALPHABET_SET})
    if bad:
        raise OrdaruglInputError(
            f"word {raw!r} contains characters not in the Icelandic alphabet: {''.join(bad)}"
        )
    return Word(display=display, placement=placement)


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


def render_pdf(out, title, grid, word_list, placements=None, highlight=False):
    """Render a PDF to `out`, which may be a path-like or a binary file-like object."""
    n = len(grid)  # grid is square
    filename = str(out) if isinstance(out, (str, Path)) else out
    c = canvas.Canvas(filename, pagesize=A4)

    # Title bar (top-left blue strip).
    title_h = 14 * mm
    c.setFont("Helvetica-Bold", 20)
    title_w = max(80 * mm, c.stringWidth(title, "Helvetica-Bold", 20) + 18 * mm)
    title_y = PAGE_H - MARGIN - title_h
    c.setFillColor(TITLE_BLUE)
    c.rect(MARGIN, title_y, title_w, title_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.drawString(MARGIN + 6 * mm, title_y + 4.6 * mm, title)

    # --- Layout: the grid is the priority; word list fits in what's left ---
    border_pad = 4 * mm
    gap_after_title = 8 * mm
    gap_before_list = 10 * mm

    avail_w_grid = PAGE_W - 2 * MARGIN - 2 * border_pad
    cell_from_width = avail_w_grid / n  # grid cell size if width is the limit

    # Word list parameters (font size determined later, once grid is sized).
    list_col_w = (PAGE_W - 2 * MARGIN) / LIST_COLS
    # Word list is rendered exactly as supplied (preserves spaces, dashes, casing).
    displayed = list(word_list)
    longest_display = max((len(d) for d in displayed), default=1)
    font_from_width = (list_col_w * 0.90) / (longest_display * 0.55)
    desired_font = min(LIST_FONT_MAX, font_from_width)
    list_rows = math.ceil(len(word_list) / LIST_COLS) if word_list else 0

    # Total vertical between title and bottom margin, minus fixed gaps and pads.
    total_v = title_y - MARGIN - gap_after_title - 2 * border_pad - gap_before_list

    # Step 1: reserve only the *minimum* the word list needs, so the grid
    # always wins as much vertical space as it can.
    min_list_h = list_rows * LIST_FONT_MIN * LIST_LINE_RATIO
    max_grid_h = max(0.0, total_v - min_list_h)
    cell_from_height = max_grid_h / n if n else 0
    cell = min(cell_from_width, cell_from_height)
    grid_side = cell * n

    # Step 2: word list expands into the leftover, capped by what looks good.
    remaining_v = total_v - grid_side
    desired_list_h = list_rows * desired_font * LIST_LINE_RATIO
    actual_list_h = min(remaining_v, desired_list_h)
    if list_rows > 0:
        list_font = (actual_list_h / list_rows) / LIST_LINE_RATIO
        list_font = max(LIST_FONT_MIN, min(LIST_FONT_MAX, font_from_width, list_font))
    else:
        list_font = LIST_FONT_MIN
    list_line_h = list_font * LIST_LINE_RATIO
    list_h = list_rows * list_line_h

    grid_x = (PAGE_W - grid_side) / 2
    grid_y = title_y - gap_after_title - border_pad - grid_side

    # Push the list toward the bottom margin if there's still slack.
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


# ---------- Library API ----------

@dataclass
class PuzzleResult:
    """Output of `generate()` — two PDFs in memory plus metadata.

    Both PDF buffers are rewound to position 0, ready to be served or written.
    """
    puzzle_pdf: BytesIO
    solution_pdf: BytesIO
    requested_size: int
    final_size: int
    placed_words: list[str]    # display forms, Icelandic-sorted
    dropped_words: list[str]   # display forms of words that could not be placed


def generate(
    raw_words: list[str],
    *,
    title: str = "Orðarugl",
    difficulty: str = "medium",
    no_diagonals: bool = False,
    no_backwards: bool = False,
    size: int | None = None,
    seed: int | None = None,
) -> PuzzleResult:
    """Generate puzzle + solution PDFs from a list of raw word strings.

    Raises OrdaruglInputError on user-input problems (empty list, bad characters,
    word too long for grid, no directions enabled).
    """
    if not raw_words:
        raise OrdaruglInputError("no words supplied")
    if difficulty not in ("easy", "medium", "hard"):
        raise OrdaruglInputError(f"unknown difficulty {difficulty!r}")

    entries = [normalize_word(w) for w in raw_words]  # may raise OrdaruglInputError
    placements_words = [e.placement for e in entries]

    no_diag = no_diagonals or difficulty == "easy"
    no_back = no_backwards or difficulty in ("easy", "medium")
    directions = resolve_directions(no_diag, no_back)
    if not directions:
        raise OrdaruglInputError("no directions enabled — relax the difficulty flags")

    rng = random.Random(seed)

    longest = max(len(w) for w in placements_words)
    total_letters = sum(len(w) for w in placements_words)
    default_n = max(longest, math.ceil(math.sqrt(total_letters * 1.8)), 12)

    if size is not None:
        n = size
        user_fixed = True
    else:
        n = default_n
        user_fixed = False

    if longest > n:
        raise OrdaruglInputError(
            f"longest word ({longest} letters) doesn't fit in a {n}x{n} grid"
        )

    requested_n = n
    grid, placements, dropped, final_n = build_puzzle(
        placements_words, n, directions, rng, grow=not user_fixed
    )

    # Filler alphabet: only letters that already appear in input words (spec).
    used_letters = sorted({ch for w in placements_words for ch in w})
    fill_grid(grid, used_letters, rng)

    sorted_entries = sorted(entries, key=lambda e: icelandic_sort_key(e.placement))
    placed_entries = [e for e in sorted_entries if e.placement in placements]
    place_to_display = {e.placement: e.display for e in entries}
    dropped_display = [place_to_display.get(p, p) for p in dropped]

    puzzle_buf = BytesIO()
    solution_buf = BytesIO()
    render_pdf(
        puzzle_buf, title, grid,
        [e.display for e in sorted_entries],
        placements=placements, highlight=False,
    )
    render_pdf(
        solution_buf, f"{title} — Lausn", grid,
        [e.display for e in placed_entries],
        placements=placements, highlight=True,
    )
    puzzle_buf.seek(0)
    solution_buf.seek(0)

    return PuzzleResult(
        puzzle_pdf=puzzle_buf,
        solution_pdf=solution_buf,
        requested_size=requested_n,
        final_size=final_n,
        placed_words=[e.display for e in placed_entries],
        dropped_words=dropped_display,
    )


# ---------- CLI ----------

def read_words_from_args(args) -> list[str]:
    """Return raw word strings from --words or --words-file."""
    if args.words:
        raw = [w for w in args.words.split(",") if w.strip()]
    else:
        path = Path(args.words_file)
        if not path.exists():
            raise OrdaruglInputError(f"words file not found: {path}")
        raw = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                raw.append(line)
    if not raw:
        raise OrdaruglInputError("no words supplied")
    return raw


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

    # Flatten --size / --cols / --rows into a single size (grid is square).
    user_sizes = [s for s in (args.size, args.cols, args.rows) if s is not None]
    if user_sizes:
        size = max(user_sizes)
        if len(set(user_sizes)) > 1:
            print(
                f"Note: grid is square — using {size} (the largest of the supplied sizes).",
                file=sys.stderr,
            )
    else:
        size = None

    try:
        raw_words = read_words_from_args(args)
        result = generate(
            raw_words,
            title=args.title,
            difficulty=args.difficulty,
            no_diagonals=args.no_diagonals,
            no_backwards=args.no_backwards,
            size=size,
            seed=args.seed,
        )
    except OrdaruglInputError as e:
        sys.exit(str(e))

    if result.final_size != result.requested_size:
        print(
            f"Grew grid from {result.requested_size}x{result.requested_size} "
            f"to {result.final_size}x{result.final_size} to fit all words.",
            file=sys.stderr,
        )
    if result.dropped_words:
        print(
            f"Warning: could not place {len(result.dropped_words)} word(s): "
            f"{', '.join(result.dropped_words)}",
            file=sys.stderr,
        )

    out_path = Path(args.out)
    sol_path = out_path.with_name(out_path.stem + "-solution" + out_path.suffix)
    out_path.write_bytes(result.puzzle_pdf.getvalue())
    sol_path.write_bytes(result.solution_pdf.getvalue())

    print(f"Wrote {out_path}")
    print(f"Wrote {sol_path}")
    return 1 if result.dropped_words else 0


if __name__ == "__main__":
    sys.exit(main())
