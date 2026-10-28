"""Signed job webhooks. Receivers check X-DocFlow-Signature: sha256=<hex HMAC of the raw body>."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

import httpx

log = logging.getLogger("docflow.webhooks")


def sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def send(url: str, secret: str, event: dict) -> None:
    if not url:
        return
    body = json.dumps(event, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json", "X-DocFlow-Event": event["type"]}
    if secret:
        headers["X-DocFlow-Signature"] = sign(body, secret)
    try:
        httpx.post(url, content=body, headers=headers, timeout=5.0).raise_for_status()
    except httpx.HTTPError as ex:
        log.warning("webhook to %s failed: %s", url, ex)
