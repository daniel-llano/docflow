import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { describe, it } from "node:test";
import { verifySignature } from "./signature";

const body = Buffer.from('{"type":"job.completed","jobId":"1"}');
const good = "sha256=" + createHmac("sha256", "s3cret").update(body).digest("hex");

describe("verifySignature", () => {
  it("accepts the right signature", () => {
    assert.equal(verifySignature(body, good, "s3cret"), true);
  });

  it("rejects a wrong or missing signature", () => {
    assert.equal(verifySignature(body, good, "other"), false);
    assert.equal(verifySignature(body, undefined, "s3cret"), false);
    assert.equal(verifySignature(body, "sha256=abc", "s3cret"), false);
  });

  it("rejects a tampered body", () => {
    assert.equal(verifySignature(Buffer.from('{"jobId":"2"}'), good, "s3cret"), false);
  });

  it("skips checks when no secret is configured", () => {
    assert.equal(verifySignature(body, undefined, ""), true);
  });
});
