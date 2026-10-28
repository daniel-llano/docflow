export type JobEvent = {
  receivedAt: string;
  body: unknown;
};

export class EventStore {
  private readonly events: JobEvent[] = [];

  constructor(private readonly cap = 100) {}

  add(body: unknown): JobEvent {
    const event: JobEvent = { receivedAt: new Date().toISOString(), body };
    this.events.unshift(event);
    if (this.events.length > this.cap) {
      this.events.pop();
    }
    return event;
  }

  list(): JobEvent[] {
    return [...this.events];
  }
}
