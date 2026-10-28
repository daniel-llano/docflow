import { EventStore } from "./store";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

describe("EventStore", () => {
  it("keeps newest events first and respects cap", () => {
    const store = new EventStore(3);
    store.add({ n: 1 });
    store.add({ n: 2 });
    store.add({ n: 3 });
    store.add({ n: 4 });
    const listed = store.list();
    assert.equal(listed.length, 3);
    assert.deepEqual((listed[0].body as { n: number }).n, 4);
    assert.deepEqual((listed[2].body as { n: number }).n, 2);
  });
});
