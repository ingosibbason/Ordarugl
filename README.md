# Orðarugl

A small CLI that generates printable Icelandic word search puzzles ("orðarugl")
as A4 PDFs. Pure-vector output, sharp at any print size, no headless browser.

![Example puzzle](examples/puzzle.pdf)

## Features

- Full Icelandic alphabet support: **A Á B D Ð E É F G H I Í J K L M N O Ó P R S T U Ú V X Y Ý Þ Æ Ö**
- Three difficulty presets (`easy` / `medium` / `hard`) plus fine-grained `--no-diagonals` / `--no-backwards` flags
- Auto-sized grid that grows if your words don't fit (with a warning if any get dropped)
- Filler letters drawn only from the letters that already appear in your word list — no giveaway letters
- Generates **two** PDFs every run: the puzzle, and a solution PDF with the placed words highlighted
- Reproducible output with `--seed`

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

## How it works

1. Words are normalized to uppercase and validated against the Icelandic alphabet
   — any character outside it is a hard error.
2. Words are sorted longest-first and placed at random positions/directions,
   allowed to overlap on matching letters. Up to 300 placement attempts per word.
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
