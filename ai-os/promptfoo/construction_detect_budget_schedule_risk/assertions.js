const { parsesLikeProduction } = require("../lib/assertions.js");

function parses(output) {
  return parsesLikeProduction(output);
}

function riskLevelIsValid(output) {
  const r = parsesLikeProduction(output);
  if (!r.pass) return r;
  if (!["low", "medium", "high"].includes(r.data.riskLevel)) {
    return { pass: false, score: 0, reason: `riskLevel ${JSON.stringify(r.data.riskLevel)} not one of low/medium/high` };
  }
  return { pass: true, score: 1, reason: "riskLevel is a valid enum value" };
}

function riskLevelIsHigh(output) {
  const r = parsesLikeProduction(output);
  if (!r.pass) return r;
  if (r.data.riskLevel !== "high") {
    return { pass: false, score: 0, reason: `expected riskLevel='high' for a project 40% over budget with 60% of tasks delayed, per the prompt's own "base riskLevel primarily on variance and proportion of delayed tasks" rule -- got ${JSON.stringify(r.data.riskLevel)}` };
  }
  return { pass: true, score: 1, reason: "riskLevel=high as the prompt's own variance/delay rule expects for this severely over-budget, badly-delayed input" };
}

function riskLevelIsLow(output) {
  const r = parsesLikeProduction(output);
  if (!r.pass) return r;
  if (r.data.riskLevel !== "low") {
    return { pass: false, score: 0, reason: `expected riskLevel='low' for a project on-budget with zero delayed tasks -- got ${JSON.stringify(r.data.riskLevel)}` };
  }
  return { pass: true, score: 1, reason: "riskLevel=low as expected for an on-budget, on-schedule project" };
}

module.exports = { parses, riskLevelIsValid, riskLevelIsHigh, riskLevelIsLow };
