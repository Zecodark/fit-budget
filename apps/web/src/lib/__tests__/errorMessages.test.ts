import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { ERROR_MESSAGES, formatDec1, formatIdr, formatInt, getErrorMessage } from "../errorMessages.ts";

describe("Indonesian Error Catalog & Formatters (PRD §0.2, §6.2)", () => {
  it("maps every PRD §6.2 error code to non-empty Indonesian copy", () => {
    const requiredCodes = [
      "VALIDATION_ERROR",
      "UNAUTHENTICATED",
      "FORBIDDEN",
      "NOT_FOUND",
      "EMAIL_ALREADY_REGISTERED",
      "INVALID_CREDENTIALS",
      "ACCOUNT_LOCKED",
      "CONSENT_REQUIRED",
      "AI_CLOUD_CONSENT_REQUIRED",
      "PROFESSIONAL_CONSULT_REQUIRED",
      "GOAL_NOT_ALLOWED",
      "PLAN_VERSION_CONFLICT",
      "PROPOSAL_EXPIRED",
      "PROPOSAL_INVALID",
      "OPTIMIZER_NO_CATALOG_FOODS",
      "AI_UNAVAILABLE",
      "AI_OUTPUT_REJECTED",
      "PRICE_CHANGE_CONFIRMATION_REQUIRED",
      "RATE_LIMITED",
      "INTERNAL_ERROR",
    ];
    for (const code of requiredCodes) {
      const msg = getErrorMessage(code);
      assert.ok(msg && msg.length > 10, `Missing message for ${code}`);
      assert.equal(msg, ERROR_MESSAGES[code]);
    }
  });

  it("formats IDR currency using Indonesian thousands separator without decimals", () => {
    const formatted = formatIdr(45000);
    assert.ok(formatted.includes("Rp"), `Expected Rp prefix in ${formatted}`);
    assert.ok(formatted.includes("45.000"), `Expected 45.000 in ${formatted}`);
  });

  it("formats 1-decimal numbers with Indonesian comma separator", () => {
    assert.equal(formatDec1(135.5), "135,5");
    assert.equal(formatInt(2150), "2.150");
  });

  it("never claims 'terpenuhi' in error messages for infeasible or rejected outputs", () => {
    assert.ok(!ERROR_MESSAGES.OPTIMIZER_NO_CATALOG_FOODS.toLowerCase().includes("terpenuhi"));
    assert.ok(!ERROR_MESSAGES.AI_OUTPUT_REJECTED.toLowerCase().includes("terpenuhi"));
  });
});
