// PDF rendering port of render_pdf() from ordarugl.py.
// Uses jsPDF, loaded via the ESM CDN build.

import { jsPDF } from "https://cdn.jsdelivr.net/npm/jspdf@2.5.2/+esm";

const MM = 72 / 25.4;             // 1 mm in pt
const PAGE_W = 595.275590551;     // A4 in pt
const PAGE_H = 841.889763779;
const MARGIN = 15 * MM;
const TITLE_BLUE = "#2E73B8";
const HIGHLIGHT = "#FFD93D";
const LIST_COLS = 4;
const LIST_FONT_MAX = 18;
const LIST_FONT_MIN = 8;
const LIST_LINE_RATIO = 1.55;

function renderOne(title, grid, wordList, placements = null, highlight = false) {
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const n = grid.length;

  // Title bar (top-left blue strip).
  const titleH = 14 * MM;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(20);
  const titleStrW = doc.getTextWidth(title);
  const titleW = Math.max(80 * MM, titleStrW + 18 * MM);
  doc.setFillColor(TITLE_BLUE);
  doc.rect(MARGIN, MARGIN, titleW, titleH, "F");
  doc.setTextColor("#FFFFFF");
  // ReportLab drew the title baseline at title_y + 4.6mm where title_y is the bar's bottom edge.
  // In jsPDF (top-down): baseline = MARGIN + titleH - 4.6mm.
  doc.text(title, MARGIN + 6 * MM, MARGIN + titleH - 4.6 * MM, { baseline: "alphabetic" });

  // --- Layout (numeric math is the same as in ordarugl.py) ---
  const borderPad = 4 * MM;
  const gapAfterTitle = 8 * MM;
  const gapBeforeList = 10 * MM;

  const availWGrid = PAGE_W - 2 * MARGIN - 2 * borderPad;
  const cellFromWidth = availWGrid / n;

  const listColW = (PAGE_W - 2 * MARGIN) / LIST_COLS;
  const displayed = [...wordList];
  const longestDisplay = displayed.length
    ? Math.max(...displayed.map((s) => s.length))
    : 1;
  const fontFromWidth = (listColW * 0.9) / (longestDisplay * 0.55);
  const desiredFont = Math.min(LIST_FONT_MAX, fontFromWidth);
  const listRows = wordList.length ? Math.ceil(wordList.length / LIST_COLS) : 0;

  // Vertical space available between bottom of title and top of bottom margin,
  // minus the fixed gaps and the dotted border padding (top + bottom).
  const totalV = PAGE_H - 2 * MARGIN - titleH - gapAfterTitle - 2 * borderPad - gapBeforeList;

  const minListH = listRows * LIST_FONT_MIN * LIST_LINE_RATIO;
  const maxGridH = Math.max(0, totalV - minListH);
  const cellFromHeight = n ? maxGridH / n : 0;
  const cell = Math.min(cellFromWidth, cellFromHeight);
  const gridSide = cell * n;

  const remainingV = totalV - gridSide;
  const desiredListH = listRows * desiredFont * LIST_LINE_RATIO;
  const actualListH = Math.min(remainingV, desiredListH);
  let listFont;
  if (listRows > 0) {
    listFont = actualListH / listRows / LIST_LINE_RATIO;
    listFont = Math.max(LIST_FONT_MIN, Math.min(LIST_FONT_MAX, fontFromWidth, listFont));
  } else {
    listFont = LIST_FONT_MIN;
  }
  const listLineH = listFont * LIST_LINE_RATIO;
  const listH = listRows * listLineH;

  const gridX = (PAGE_W - gridSide) / 2;
  const gridTop = MARGIN + titleH + gapAfterTitle + borderPad;

  const usedV = gridSide + listH;
  const extraV = Math.max(0, totalV - usedV);
  const listGap = gapBeforeList + extraV;

  // Dotted border around grid.
  doc.setDrawColor("#000000");
  doc.setLineWidth(0.9);
  doc.setLineDashPattern([1, 3], 0);
  doc.rect(
    gridX - borderPad,
    gridTop - borderPad,
    gridSide + 2 * borderPad,
    gridSide + 2 * borderPad,
    "S"
  );
  doc.setLineDashPattern([], 0);

  // Cell center in jsPDF (top-down) coordinates.
  const cellCenter = (r, ci) => [
    gridX + ci * cell + cell / 2,
    gridTop + (r + 0.5) * cell,
  ];

  // Solution highlights (drawn under letters so the letters remain readable).
  if (highlight && placements) {
    doc.setDrawColor(HIGHLIGHT);
    doc.setLineCap("round");
    doc.setLineWidth(cell * 0.72);
    for (const positions of placements.values()) {
      const [x0, y0] = cellCenter(...positions[0]);
      const [x1, y1] = cellCenter(...positions[positions.length - 1]);
      doc.line(x0, y0, x1, y1);
    }
    doc.setLineCap("butt");
  }

  // Letters.
  doc.setTextColor("#000000");
  const letterFont = cell * 0.58;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(letterFont);
  const yAdjust = letterFont * 0.32;
  for (let r = 0; r < n; r++) {
    for (let ci = 0; ci < n; ci++) {
      const [x, y] = cellCenter(r, ci);
      doc.text(grid[r][ci], x, y + yAdjust, { align: "center", baseline: "alphabetic" });
    }
  }

  // Word list — column-major, 4 columns, dynamic font size.
  if (wordList.length > 0) {
    const perCol = Math.ceil(wordList.length / LIST_COLS);
    const firstBaseline = gridTop + gridSide + borderPad + listGap + listFont * 0.85;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(listFont);
    doc.setTextColor("#000000");
    for (let i = 0; i < displayed.length; i++) {
      const colIdx = Math.floor(i / perCol);
      const rowIdx = i % perCol;
      const x = MARGIN + colIdx * listColW;
      const y = firstBaseline + rowIdx * listLineH;
      doc.text(displayed[i], x, y, { align: "left", baseline: "alphabetic" });
    }
  }

  return doc;
}

// Render puzzle + solution PDFs from a buildResult() output. Returns Blobs ready to download.
export function renderTwoPdfs(result, title) {
  const puzzleDoc = renderOne(title, result.grid, result.fullWordList, result.placements, false);
  const solutionDoc = renderOne(
    `${title} — Lausn`,
    result.grid,
    result.placedWordList,
    result.placements,
    true
  );
  return {
    puzzleBlob: puzzleDoc.output("blob"),
    solutionBlob: solutionDoc.output("blob"),
  };
}
