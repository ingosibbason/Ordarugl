import { buildResult, OrdaruglInputError } from "./ordarugl.js";
import { renderTwoPdfs } from "./pdf.js";

const SAMPLE_WORDS = [
  "REYKJAVÍK",
  "KÓPAVOGUR",
  "HAFNARFJÖRÐUR",
  "AKUREYRI",
  "SELFOSS",
  "EGILSSTAÐIR",
  "ÍSAFJÖRÐUR",
  "VESTMANNAEYJAR",
  "BORGARNES",
  "HÚSAVÍK",
  "SAUÐÁRKRÓKUR",
  "KEFLAVÍK",
];

const MAX_WORDS = 100;
const MAX_GRID_SIDE = 30;

const $ = (sel) => document.querySelector(sel);

const form = $("#form");
const wordsEl = $("#words");
const titleEl = $("#title");
const sizeEl = $("#size");
const generateBtn = $("#generate");
const sampleBtn = $("#sample");
const resultEl = $("#result");
const dlPuzzle = $("#dl-puzzle");
const dlSolution = $("#dl-solution");
const metaEl = $("#meta");
const warningsEl = $("#warnings");
const errorsEl = $("#errors");
const wordCountEl = $("#word-count");
const previewWrapperEl = $("#preview-wrapper");
const previewGridEl = $("#preview-grid");
const previewOverlayEl = $("#preview-overlay");
const showSolutionEl = $("#show-solution");

const SVG_NS = "http://www.w3.org/2000/svg";

function renderPreview(result) {
  const n = result.grid.length;

  previewGridEl.style.setProperty("--grid-n", n);
  previewGridEl.style.gridTemplateColumns = `repeat(${n}, 1fr)`;
  previewGridEl.style.gridTemplateRows = `repeat(${n}, 1fr)`;
  previewGridEl.replaceChildren(previewOverlayEl);
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      const div = document.createElement("div");
      div.className = "preview-cell";
      div.textContent = result.grid[r][c];
      previewGridEl.appendChild(div);
    }
  }

  previewOverlayEl.setAttribute("viewBox", `0 0 ${n} ${n}`);
  previewOverlayEl.setAttribute("preserveAspectRatio", "none");
  previewOverlayEl.replaceChildren();
  for (const positions of result.placements.values()) {
    const [r0, c0] = positions[0];
    const [r1, c1] = positions[positions.length - 1];
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", c0 + 0.5);
    line.setAttribute("y1", r0 + 0.5);
    line.setAttribute("x2", c1 + 0.5);
    line.setAttribute("y2", r1 + 0.5);
    previewOverlayEl.appendChild(line);
  }

  showSolutionEl.checked = false;
  previewWrapperEl.classList.remove("show-solution");
}

let lastPuzzleUrl = null;
let lastSolutionUrl = null;

function showError(msg) {
  errorsEl.textContent = msg;
  errorsEl.hidden = false;
  resultEl.hidden = true;
}

function clearError() {
  errorsEl.hidden = true;
  errorsEl.textContent = "";
}

function revokeLastUrls() {
  if (lastPuzzleUrl) { URL.revokeObjectURL(lastPuzzleUrl); lastPuzzleUrl = null; }
  if (lastSolutionUrl) { URL.revokeObjectURL(lastSolutionUrl); lastSolutionUrl = null; }
}

function parseRawWords(text) {
  // Accept newlines OR commas as separators.
  return text
    .split(/[\n,]+/)
    .map((w) => w.trim())
    .filter((w) => w.length > 0);
}

function safeFilenameBase(title) {
  // Keep Icelandic letters; strip filesystem-unfriendly chars.
  const base = title.trim().replace(/[\\/:*?"<>|]+/g, "").replace(/\s+/g, "_");
  return base || "ordarugl";
}

function getDifficulty() {
  const checked = form.querySelector('input[name="difficulty"]:checked');
  return checked ? checked.value : "medium";
}

async function handleGenerate(event) {
  event.preventDefault();
  clearError();

  const rawWords = parseRawWords(wordsEl.value);
  if (rawWords.length === 0) {
    showError("Settu inn að minnsta kosti eitt orð.");
    return;
  }
  if (rawWords.length > MAX_WORDS) {
    showError(`Hámark er ${MAX_WORDS} orð. Þú settir inn ${rawWords.length}.`);
    return;
  }

  const titleValue = titleEl.value.trim() || "Orðarugl";
  const difficulty = getDifficulty();

  const sizeRaw = sizeEl.value.trim();
  let size = null;
  if (sizeRaw) {
    const parsed = parseInt(sizeRaw, 10);
    if (!Number.isFinite(parsed) || parsed < 5) {
      showError("Stærð grindar verður að vera að minnsta kosti 5.");
      return;
    }
    if (parsed > MAX_GRID_SIDE) {
      showError(`Hámarksstærð grindar er ${MAX_GRID_SIDE}×${MAX_GRID_SIDE}.`);
      return;
    }
    size = parsed;
  }

  generateBtn.disabled = true;
  generateBtn.textContent = "Bý til…";

  try {
    // Let the browser paint the disabled state before the (synchronous) work runs.
    await new Promise((r) => requestAnimationFrame(() => r()));

    const result = buildResult(rawWords, { difficulty, size });

    if (result.finalSize > MAX_GRID_SIDE) {
      showError(`Stafagrindin þurfti að verða ${result.finalSize}×${result.finalSize} til að rúma orðin — það er meira en hámarkið (${MAX_GRID_SIDE}×${MAX_GRID_SIDE}). Fjarlægðu nokkur orð og reyndu aftur.`);
      return;
    }

    renderPreview(result);

    const { puzzleBlob, solutionBlob } = renderTwoPdfs(result, titleValue);

    revokeLastUrls();
    lastPuzzleUrl = URL.createObjectURL(puzzleBlob);
    lastSolutionUrl = URL.createObjectURL(solutionBlob);

    const base = safeFilenameBase(titleValue);
    dlPuzzle.href = lastPuzzleUrl;
    dlPuzzle.download = `${base}.pdf`;
    dlSolution.href = lastSolutionUrl;
    dlSolution.download = `${base}-lausn.pdf`;

    const placedCount = result.placedWordList.length;
    metaEl.textContent = `${placedCount} orð raðað í ${result.finalSize}×${result.finalSize} grindi.`;

    if (result.droppedWords.length > 0) {
      warningsEl.hidden = false;
      warningsEl.textContent =
        `Ekki tókst að koma þessum orðum fyrir: ${result.droppedWords.join(", ")}.`;
    } else {
      warningsEl.hidden = true;
      warningsEl.textContent = "";
    }

    resultEl.hidden = false;
    resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    if (err instanceof OrdaruglInputError) {
      showError(err.message);
    } else {
      console.error(err);
      showError("Það kom upp óvænt villa við að búa til orðaruglið.");
    }
  } finally {
    generateBtn.disabled = false;
    generateBtn.textContent = "Búa til";
  }
}

function handleSample() {
  wordsEl.value = SAMPLE_WORDS.join("\n");
  wordsEl.focus();
  wordsEl.scrollTop = 0;
  updateWordCount();
}

function updateWordCount() {
  const count = parseRawWords(wordsEl.value).length;
  wordCountEl.textContent = `${count} orð`;
  wordCountEl.classList.toggle("over", count > MAX_WORDS);
}

form.addEventListener("submit", handleGenerate);
sampleBtn.addEventListener("click", handleSample);
wordsEl.addEventListener("input", updateWordCount);
showSolutionEl.addEventListener("change", () => {
  previewWrapperEl.classList.toggle("show-solution", showSolutionEl.checked);
});
window.addEventListener("beforeunload", revokeLastUrls);

updateWordCount();
