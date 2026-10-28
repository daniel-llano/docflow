import { Controller, Get, Headers, HttpCode, Post, Req, UnauthorizedException, type RawBodyRequest } from "@nestjs/common";
import type { Request } from "express";
import { verifySignature } from "./signature";
import { EventStore } from "./store";

@Controller()
export class EventsController {
  private readonly secret = process.env.WEBHOOK_SECRET ?? "";

  constructor(private readonly store: EventStore) {}

  @Get("health")
  health() {
    return { status: "ok", signed: this.secret.length > 0 };
  }

  @Post("webhooks/jobs")
  @HttpCode(202)
  receive(@Req() req: RawBodyRequest<Request>, @Headers("x-docflow-signature") signature?: string) {
    if (!verifySignature(req.rawBody ?? Buffer.alloc(0), signature, this.secret)) {
      throw new UnauthorizedException("Bad or missing signature.");
    }
    return { received: this.store.add(req.body).receivedAt };
  }

  @Get("events")
  list() {
    return this.store.list();
  }
}
