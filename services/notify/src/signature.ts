import { createHmac, timingSafeEqual } from "node:crypto";

/** Checks X-DocFlow-Signature: sha256=<hex HMAC-SHA256 of the raw body>. */
export function verifySignature(rawBody: Buffer, header: string | undefined, secret: string): boolean {
  if (!secret) return true;
  if (!header?.startsWith("sha256=")) return false;
  const expected = Buffer.from("sha256=" + createHmac("sha256", secret).update(rawBody).digest("hex"));
  const sent = Buffer.from(header);
  return sent.length === expected.length && timingSafeEqual(sent, expected);
}
