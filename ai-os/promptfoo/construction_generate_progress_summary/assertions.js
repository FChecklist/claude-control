const { parsesLikeProduction, extractNumbers } = require("../lib/assertions.js");

function parses(output) {
  return parsesLikeProduction(output);
}

function shapeIsValid(output) {
  const r = parsesLikeProduction(output);
  if (!r.pass) return r;
  const { summary, highlights, concerns } = r.data;
  if (typeof summary !== "string" || !Array.isArray(highlights) || !Array.isArray(concerns)) {
    return { pass: false, score: 0, reason: `output missing/mistyped required keys: ${JSON.stringify(r.data)}` };
  }
  return { pass: true, score: 1, reason: "summary/highlights/concerns present with the right types" };
}

// Prompt's own CRITICAL instruction: "only ever state numbers that appear
// in the JSON you were given -- never estimate, round dramatically, or
// invent a figure that isn't present in the input." Real hallucination
// check against the actual input numbers passed via the `input_numbers`
// test var.
function noInventedNumbers(output, context) {
  const r = parsesLikeProduction(output);
  if (!r.pass) return r;
  const allowedNumbers = new Set((context.vars.input_numbers || []).map(Number));
  const text = [r.data.summary, ...(r.data.highlights || []), ...(r.data.concerns || [])].join(" ");
  const written = extractNumbers(text);
  const invented = written.filter((n) => !allowedNumbers.has(n));
  if (invented.length > 0) {
    return { pass: false, score: 0, reason: `output states number(s) not present in the real input given: ${JSON.stringify(invented)} (input numbers were: ${JSON.stringify([...allowedNumbers])})` };
  }
  return { pass: true, score: 1, reason: "every number in the output traces back to the real input" };
}

// Prompt's own instruction: "If a number needed for a complete picture is
// missing from the input, say so explicitly rather than guessing it."
function acknowledgesMissingData(output) {
  const r = parsesLikeProduction(output);
  if (!r.pass) return r;
  const text = [r.data.summary, ...(r.data.highlights || []), ...(r.data.concerns || [])].join(" ").toLowerCase();
  if (!/missing|not (?:provided|available)|no data|unavailable|unknown/.test(text)) {
    return { pass: false, score: 0, reason: `attendance/labour data was omitted from the input, but the output never acknowledges the gap (prompt's own instruction: "say so explicitly rather than guessing it") -- output: ${JSON.stringify(r.data)}` };
  }
  return { pass: true, score: 1, reason: "output explicitly acknowledges the missing input data as the prompt requires" };
}

module.exports = { parses, shapeIsValid, noInventedNumbers, acknowledgesMissingData };
