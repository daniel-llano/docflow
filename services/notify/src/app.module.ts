import { Module } from "@nestjs/common";
import { EventsController } from "./events.controller";
import { EventStore } from "./store";

@Module({
  controllers: [EventsController],
  providers: [EventStore],
})
export class AppModule {}
