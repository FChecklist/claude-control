// VERIDIAN Auditor Engine -- Phase 6, ai-governance domain: shared
// deterministic (no LLM call inside any of these) assertion helpers for
// the promptfoo test suites under ai-os/promptfoo/*/promptfooconfig.yaml.
//
// stripJsonFence() is copied verbatim from the REAL production function of
// the same name in compliance-tracker's src/lib/llm-client.ts (used by the
// actual callLLMJson() every one of these prompts' real call sites goes
// through) -- so "parsesLikeProduction" tests the exact parse behavior
// production code has, not an arbitrary stricter standard. A prompt whose
// output fails this check would genuinely throw in production, not just
// look untidy in a test report.

function stripJsonFence(content) {
  const trimmed = content.trim();
  const fenced = trimmed.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  return fenced ? fenced[1].trim() : trimmed;
}

function parsesLikeProduction(output) {
  try {
    const data = JSON.parse(stripJsonFence(output));
    return { pass: true, score: 1, reason: "parses via production's stripJsonFence()+JSON.parse", data };
  } catch (e) {
    return { pass: false, score: 0, reason: `production's stripJsonFence()+JSON.parse would throw on this real output: ${e.message}` };
  }
}

// Extracts every standalone integer/decimal number literal from a string,
// for the two "never invent a number not in the input" prompt checks
// (gst.ai_review_report / construction.generate_progress_summary, both of
// which explicitly instruct this). Deliberately coarse (word-boundary
// numbers only, no currency-symbol stripping beyond commas) -- false
// negatives (missing a real hallucinated number written as e.g. "5%")
// are possible, but every number this DOES catch is a real, unambiguous
// literal the model wrote that must be traceable to the input.
function extractNumbers(text) {
  const matches = text.match(/-?\d[\d,]*(?:\.\d+)?/g) || [];
  return matches.map((m) => Number(m.replace(/,/g, ""))).filter((n) => !Number.isNaN(n));
}

module.exports = { stripJsonFence, parsesLikeProduction, extractNumbers };
