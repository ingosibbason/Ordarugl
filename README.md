# Orðarugl

A small tool for generating printable Icelandic word search puzzles
("orðarugl") as A4 PDFs — usable as a CLI, a Python library, or a client-side
web app. Pure-vector output, sharp at any print size.

![Example puzzle](examples/puzzle.pdf)

## Features

- Full Icelandic alphabet support: **A Á B D Ð E É F G H I Í J K L M N O Ó P R S T U Ú V X Y Ý Þ Æ Ö**
- Three difficulty presets (`easy` / `medium` / `hard`) plus fine-grained `--no-diagonals` / `--no-backwards` flags
- Auto-sized grid that grows if your words don't fit (with a warning if any get dropped)
- Filler letters drawn only from the letters that already appear in your word list — no giveaway letters
- Generates **two** PDFs every run: the puzzle, and a solution PDF with the placed words highlighted
- Reproducible output with `--seed`
- Three interfaces from the same codebase: **CLI**, a **Python library** (`from ordarugl import generate`), and a **static web app** under [`web/`](web/) that runs entirely in the browser

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/<you>/Ordarugl.git
cd Ordarugl
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Inline word list:

```bash
python ordarugl.py \
    --words "REYKJAVÍK,HRAUN,JÖKULL,GEYSIR,FOSS" \
    --out puzzle.pdf
```

From a file (one word per line, `#` for comments):

```bash
python ordarugl.py --words-file examples/words.txt --out puzzle.pdf
```

Each run writes both `<out>.pdf` (the puzzle) and `<out>-solution.pdf`
(the same grid with placed words highlighted in yellow for the maker).

### Options

| Flag                     | Default     | Meaning                                                                 |
| ------------------------ | ----------- | ----------------------------------------------------------------------- |
| `--words STR`            | —           | Comma-separated word list (mutually exclusive with `--words-file`)      |
| `--words-file PATH`      | —           | Text file with one word per line                                        |
| `--cols N`               | auto        | Grid columns. Auto-sized to fit if omitted.                             |
| `--rows N`               | auto        | Grid rows. Auto-sized to fit if omitted.                                |
| `--title STR`            | `Orðarugl`  | Title shown in the blue bar                                             |
| `--difficulty LEVEL`     | `medium`    | `easy` = →↓ only · `medium` = + ↘ diagonal · `hard` = all 8 directions  |
| `--no-diagonals`         | off         | Force-disable diagonals (combined with `--difficulty`)                  |
| `--no-backwards`         | off         | Force-disable backwards placements                                      |
| `--out PATH`             | `puzzle.pdf`| Output PDF; solution is written to `<stem>-solution.pdf`                |
| `--seed N`               | random      | Random seed for reproducible puzzles                                    |

The difficulty preset and the explicit flags combine using the **more
restrictive** of the two — so `--difficulty hard --no-backwards` is the same as
"all 8 directions but words read forward only".

### Examples

Easy puzzle, no diagonals, no reversed words:

```bash
python ordarugl.py --words-file words.txt --difficulty easy --out easy.pdf
```

Hard puzzle, all 8 directions, fixed grid size, reproducible:

```bash
python ordarugl.py --words-file words.txt --difficulty hard --cols 18 --rows 20 --seed 7 --out hard.pdf
```

## Use as a Python library

The CLI is a thin wrapper around a top-level `generate()` function. You can
call it directly and get both PDFs back as in-memory `BytesIO` buffers — handy
for wiring the generator into a web framework (Flask, FastAPI, …) or a larger
pipeline.

```python
from ordarugl import generate, OrdaruglInputError

try:
    result = generate(
        ["REYKJAVÍK", "HRAUN", "JÖKULL", "GEYSIR"],
        title="Mín orð",
        difficulty="medium",
        seed=42,
    )
except OrdaruglInputError as e:
    # User-input problem (empty list, non-Icelandic letter, word too long, …).
    print(f"Bad input: {e}")
else:
    with open("puzzle.pdf", "wb") as f:
        f.write(result.puzzle_pdf.getvalue())
    with open("puzzle-solution.pdf", "wb") as f:
        f.write(result.solution_pdf.getvalue())
    print(f"Placed {len(result.placed_words)} word(s) in a "
          f"{result.final_size}×{result.final_size} grid.")
    if result.dropped_words:
        print(f"Could not place: {result.dropped_words}")
```

The returned `PuzzleResult` exposes:

| Field            | Type          | Meaning                                                    |
| ---------------- | ------------- | ---------------------------------------------------------- |
| `puzzle_pdf`     | `BytesIO`     | The puzzle PDF, rewound to position 0.                     |
| `solution_pdf`   | `BytesIO`     | The solution PDF (placed words highlighted), rewound.      |
| `requested_size` | `int`         | Grid side originally asked for.                            |
| `final_size`     | `int`         | Grid side actually used (may have grown to fit all words). |
| `placed_words`   | `list[str]`   | Display forms of words that landed in the grid.            |
| `dropped_words`  | `list[str]`   | Display forms of words that could not be placed.           |

## Run as a website

A small client-side single-page app under [`web/`](web/) ports the puzzle
generator and PDF renderer to JavaScript. No backend required — everything
runs in the browser, and the word list never leaves the user's machine.

To run it locally:

```bash
python3 -m http.server 8765 --directory web
```

Then open `http://localhost:8765/` and you can paste a word list, pick a
difficulty, and download puzzle + solution PDFs.

Implementation notes:

- Pure ES modules; PDF generation uses [jsPDF](https://github.com/parallax/jsPDF) loaded from the jsdelivr CDN.
- Must be served over `http://` (not opened as `file://`) because of ES module imports.
- The Python implementation in [`ordarugl.py`](ordarugl.py) remains the reference; the JS port mirrors its placement algorithm and PDF layout.

## How it works

1. Words are normalized to uppercase and validated against the Icelandic alphabet
   — any character outside it is a hard error.
2. Words are sorted longest-first and placed at random positions/directions,
   allowed to cross on matching letters. Up to 300 placement attempts per word.
   Two placement rules keep crossings readable:
   - A word may not start or end on the start or end letter of a word running
     along the same line — `MÚR` + `RÚMFÖT` sharing the `R` would read
     `MÚRÚMFÖT`. Crossing that same `R` from another direction is fine, so
     `MÚR` running down into a horizontal `RÚMFÖT` is allowed.
   - Neither word may sit entirely inside another word's letters, so `RÚM` is
     never placed on three of `RÚMFÖT`'s cells.

   Opposite directions count as the same line (E/W, N/S, NE/SW, NW/SE), since
   the letters run together either way.
3. If any words don't fit, the grid grows by 1 row + 1 column and the whole
   pack is retried, up to 20 times. Any words still unplaceable are reported.
4. Remaining cells are filled with random letters drawn from the set of letters
   actually used by your input — so a puzzle made of common letters doesn't get
   a giveaway `Þ` sitting in the filler.
5. Both PDFs are rendered with ReportLab as vector content.

## Layout

The PDF mirrors the classic Icelandic newspaper word-search look:

- Blue title bar in the top-left
- Dotted rectangular border around the grid
- Uppercase letters in a bold sans-serif (Helvetica), evenly spaced in square cells
- Word list below the grid in 4 columns, rendered Title-Case

See [examples/puzzle.pdf](examples/puzzle.pdf) and
[examples/puzzle-solution.pdf](examples/puzzle-solution.pdf) for the result of:

```bash
python ordarugl.py --words-file examples/words.txt --seed 42 --out examples/puzzle.pdf
```

## License

[MIT](LICENSE)
