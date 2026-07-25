const { parsesLikeProduction, extractNumbers } = require("../lib/assertions.js");

function parses(output) {
  return parsesLikeProduction(output);
}

function verdictIsValid(output) {
  const r = parsesLikeProduction(output);
  if (!r.pass) return r;
  if (!["low", "medium", "high"].includes(r.data.verdict)) {
    return { pass: false, score: 0, reason: `verdict ${JSON.stringify(r.data.verdict)} not one of low/medium/high` };
  }
  return { pass: true, score: 1, reason: "verdict is a valid enum value" };
}

// Prompt's own explicit instruction #5: "Keep the whole report under 400
// words." A hard 400 cutoff would be flaky against real model variance, so
// this flags only a real, material overshoot (>600 words = 50% over the
// prompt's own stated ceiling) rather than nitpicking single-word drift.
function reportUnder400WordsWithBuffer(output) {
  const r = parsesLikeProduction(output);
  if (!r.pass) return r;
  const wordCount = String(r.data.reportText || "").trim().split(/\s+/).filter(Boolean).length;
  if (wordCount > 600) {
    return { pass: false, score: 0, reason: `reportText is ${wordCount} words, materially over the prompt's own "under 400 words" instruction (600-word buffer exceeded)` };
  }
  return { pass: true, score: 1, reason: `reportText is ${wordCount} words, within a reasonable buffer of the prompt's 400-word ceiling` };
}

// Prompt's own explicit instruction: "Do not recompute or contradict any
// number given to you -- treat every figure in the input as ground truth."
// This is a real hallucination check: every standalone number the model
// writes in reportText/topIssues must trace back to a number that was
// actually present in the input JSON it was given (passed in via the
// `input_numbers` test var, computed once from the real input fixture,
// not re-derived by the model).
function noInventedNumbers(output, context) {
  const r = parsesLikeProduction(output);
  if (!r.pass) return r;
  const allowedNumbers = new Set((context.vars.input_numbers || []).map(Number));
  const reportText = String(r.data.reportText || "");
  const issueAmounts = (r.data.topIssues || []).map((i) => i.amountAtStake).filter((n) => typeof n === "number");
  // Numbers < 10 are excluded from this check -- markdown list markers
  // ("1.", "2.") and small ordinal/count fragments produce false positives
  // unrelated to the real hallucination risk this check targets (a
  // materially wrong rupee figure or count), same reasoning as this file's
  // sibling construction_generate_progress_summary suite.
  const written = [...extractNumbers(reportText), ...issueAmounts].filter((n) => Math.abs(n) >= 10);
  const invented = written.filter((n) => !allowedNumbers.has(n));
  if (invented.length > 0) {
    return { pass: false, score: 0, reason: `output states number(s) not present in the real input given: ${JSON.stringify(invented)} (input numbers were: ${JSON.stringify([...allowedNumbers])})` };
  }
  return { pass: true, score: 1, reason: "every number in the output traces back to the real input" };
}

module.exports = { parses, verdictIsValid, reportUnder400WordsWithBuffer, noInventedNumbers };
