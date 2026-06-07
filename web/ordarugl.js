// JS port of the puzzle-placement logic from ordarugl.py.
// Pure logic — no DOM, no PDF. Mirrors the Python reference implementation.

export const ALPHABET = Array.from("AÁBCDÐEÉFGHIÍJKLMNOÓPQRSTUÚVWXYÝZÞÆÖ");
export const ALPHABET_SET = new Set(ALPHABET);
export const ALPHABET_ORDER = new Map(ALPHABET.map((ch, i) => [ch, i]));

export function icelandicSortKey(word) {
  const upper = word.toUpperCase();
  const out = new Array(upper.length);
  for (let i = 0; i < upper.length; i++) {
    const v = ALPHABET_ORDER.get(upper[i]);
    out[i] = v === undefined ? ALPHABET.length : v;
  }
  return out;
}

function compareKeys(a, b) {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return a.length - b.length;
}

export const DIR_E  = [0, 1];
export const DIR_S  = [1, 0];
export const DIR_SE = [1, 1];
export const DIR_W  = [0, -1];
export const DIR_N  = [-1, 0];
export const DIR_NW = [-1, -1];
export const DIR_NE = [-1, 1];
export const DIR_SW = [1, -1];

const ALL_DIRS = [DIR_E, DIR_S, DIR_SE, DIR_W, DIR_N, DIR_NW, DIR_NE, DIR_SW];
const DIAGONAL_KEYS = new Set(["1,1", "-1,-1", "-1,1", "1,-1"]);
const FORWARD_KEYS = new Set(["0,1", "1,0", "1,1"]);

const dirKey = (d) => `${d[0]},${d[1]}`;

export function resolveDirections({ noDiagonals = false, noBackwards = false } = {}) {
  return ALL_DIRS.filter((d) => {
    const k = dirKey(d);
    if (noDiagonals && DIAGONAL_KEYS.has(k)) return false;
    if (noBackwards && !FORWARD_KEYS.has(k)) return false;
    return true;
  });
}

// Characters allowed inside user input but stripped before placement.
const SEPARATORS = new Set([" ", "\t", "-", "–", "—"]);

export class OrdaruglInputError extends Error {
  constructor(message) {
    super(message);
    this.name = "OrdaruglInputError";
  }
}

export function normalizeWord(raw) {
  const display = raw.trim().split(/\s+/).join(" ");
  if (!display) {
    throw new OrdaruglInputError("Tómt orð.");
  }
  let placement = "";
  for (const ch of display.toUpperCase()) {
    if (!SEPARATORS.has(ch)) placement += ch;
  }
  if (!placement) {
    throw new OrdaruglInputError(`Orðið „${raw}“ inniheldur enga bókstafi.`);
  }
  const bad = [];
  const seen = new Set();
  for (const ch of placement) {
    if (!ALPHABET_SET.has(ch) && !seen.has(ch)) {
      seen.add(ch);
      bad.push(ch);
    }
  }
  if (bad.length > 0) {
    bad.sort();
    throw new OrdaruglInputError(
      `Orðið „${raw}“ inniheldur stafi sem eru ekki í íslenska stafrófinu: ${bad.join("")}`
    );
  }
  return { display, placement };
}

// Mulberry32 — small seedable PRNG. Output is deterministic for the same seed.
export function makeRng(seed) {
  let a = (seed >>> 0) || 1;
  return function () {
    a |= 0;
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function randint(rng, lo, hi) {
  return lo + Math.floor(rng() * (hi - lo + 1));
}

function pick(rng, arr) {
  return arr[Math.floor(rng() * arr.length)];
}

function tryPlace(grid, word, directions, rng, maxAttempts = 300) {
  const rows = grid.length;
  const cols = grid[0].length;
  const n = word.length;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const [dr, dc] = pick(rng, directions);
    let rLo, rHi, cLo, cHi;
    if (dr > 0) { rLo = 0; rHi = rows - n; }
    else if (dr < 0) { rLo = n - 1; rHi = rows - 1; }
    else { rLo = 0; rHi = rows - 1; }
    if (dc > 0) { cLo = 0; cHi = cols - n; }
    else if (dc < 0) { cLo = n - 1; cHi = cols - 1; }
    else { cLo = 0; cHi = cols - 1; }
    if (rLo > rHi || cLo > cHi) continue;
    const r = randint(rng, rLo, rHi);
    const c = randint(rng, cLo, cHi);
    let ok = true;
    for (let i = 0; i < n; i++) {
      const cell = grid[r + dr * i][c + dc * i];
      if (cell !== null && cell !== word[i]) { ok = false; break; }
    }
    if (!ok) continue;
    const cells = [];
    for (let i = 0; i < n; i++) {
      const pr = r + dr * i;
      const pc = c + dc * i;
      grid[pr][pc] = word[i];
      cells.push([pr, pc]);
    }
    return cells;
  }
  return null;
}

function emptyGrid(n) {
  const g = new Array(n);
  for (let r = 0; r < n; r++) {
    g[r] = new Array(n).fill(null);
  }
  return g;
}

function buildPuzzle(words, n, directions, rng, grow = true, maxGrows = 20) {
  // Place words on a square n×n grid, optionally growing until everything fits.
  const sorted = [...words].sort((a, b) => b.length - a.length);
  let size = n;
  for (let attempt = 0; attempt < (grow ? maxGrows : 1); attempt++) {
    const grid = emptyGrid(size);
    const placements = new Map();
    const dropped = [];
    for (const w of sorted) {
      const pos = tryPlace(grid, w, directions, rng);
      if (pos === null) dropped.push(w);
      else placements.set(w, pos);
    }
    if (dropped.length === 0) {
      return { grid, placements, dropped: [], size };
    }
    if (!grow) {
      return { grid, placements, dropped, size };
    }
    size += 1;
  }
  // Last attempt's state is the best we have.
  const grid = emptyGrid(size);
  const placements = new Map();
  const dropped = [];
  for (const w of sorted) {
    const pos = tryPlace(grid, w, directions, rng);
    if (pos === null) dropped.push(w);
    else placements.set(w, pos);
  }
  return { grid, placements, dropped, size };
}

function fillGrid(grid, lettersPool, rng) {
  for (let r = 0; r < grid.length; r++) {
    for (let c = 0; c < grid[0].length; c++) {
      if (grid[r][c] === null) grid[r][c] = pick(rng, lettersPool);
    }
  }
}

// High-level entry point: prepares a placed-and-filled grid plus sorted word lists.
// Does NOT render PDFs — that lives in pdf.js. Throws OrdaruglInputError on bad input.
export function buildResult(
  rawWords,
  { difficulty = "medium", noDiagonals = false, noBackwards = false, size = null, seed = null } = {}
) {
  if (!rawWords || rawWords.length === 0) {
    throw new OrdaruglInputError("Engin orð gefin.");
  }
  if (!["easy", "medium", "hard"].includes(difficulty)) {
    throw new OrdaruglInputError(`Óþekkt erfiðleikastig: ${difficulty}`);
  }

  const entries = rawWords.map(normalizeWord); // may throw
  const placementsWords = entries.map((e) => e.placement);

  const effNoDiag = noDiagonals || difficulty === "easy";
  const effNoBack = noBackwards || difficulty === "easy" || difficulty === "medium";
  const directions = resolveDirections({ noDiagonals: effNoDiag, noBackwards: effNoBack });
  if (directions.length === 0) {
    throw new OrdaruglInputError("Engin átt valin — slakaðu á erfiðleikastillingunum.");
  }

  // Seed: integer (anything truthy works). Random if null/undefined.
  const seedVal = seed == null ? Math.floor(Math.random() * 0xFFFFFFFF) : seed;
  const rng = makeRng(seedVal);

  const longest = Math.max(...placementsWords.map((w) => w.length));
  const totalLetters = placementsWords.reduce((s, w) => s + w.length, 0);
  const defaultN = Math.max(longest, Math.ceil(Math.sqrt(totalLetters * 1.8)), 12);

  let n, userFixed;
  if (size != null) {
    n = size;
    userFixed = true;
  } else {
    n = defaultN;
    userFixed = false;
  }

  if (longest > n) {
    throw new OrdaruglInputError(
      `Lengsta orðið (${longest} stafir) passar ekki í ${n}×${n} reit.`
    );
  }

  const requestedN = n;
  const { grid, placements, dropped, size: finalN } = buildPuzzle(
    placementsWords, n, directions, rng, !userFixed
  );

  const usedLettersSet = new Set();
  for (const w of placementsWords) for (const ch of w) usedLettersSet.add(ch);
  const usedLetters = Array.from(usedLettersSet).sort();
  fillGrid(grid, usedLetters, rng);

  const sortedEntries = [...entries].sort((a, b) =>
    compareKeys(icelandicSortKey(a.placement), icelandicSortKey(b.placement))
  );
  const placedEntries = sortedEntries.filter((e) => placements.has(e.placement));
  const placeToDisplay = new Map(entries.map((e) => [e.placement, e.display]));
  const droppedDisplay = dropped.map((p) => placeToDisplay.get(p) ?? p);

  return {
    grid,
    placements,
    requestedSize: requestedN,
    finalSize: finalN,
    fullWordList: sortedEntries.map((e) => e.display),       // every input word, sorted
    placedWordList: placedEntries.map((e) => e.display),     // only successfully placed
    droppedWords: droppedDisplay,
  };
}
