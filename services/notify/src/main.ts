import "reflect-metadata";
import { NestFactory } from "@nestjs/core";
import { AppModule } from "./app.module";

async function bootstrap() {
  if (process.env.NODE_ENV === "production" && !process.env.WEBHOOK_SECRET) {
    throw new Error("Set WEBHOOK_SECRET so unsigned webhooks are rejected.");
  }
  const app = await NestFactory.create(AppModule, { rawBody: true });
  app.enableShutdownHooks();
  await app.listen(Number(process.env.PORT ?? 8090));
}

void bootstrap();
