# Testing DocFlow

## Unit and integration

```bash
./scripts/test.sh
```

```powershell
.\scripts\test.ps1
```

- `services/api/tests`: pytest against the FastAPI app on in-memory SQLite.
  - `test_api.py`: auth, ownership, uploads (type and size limits), paging, delete, retry, internal-key checks, and that no default user exists.
  - `test_pipeline.py`: PII masking (including Luhn checks and dates that look like phone numbers), language detection, amounts, dates, file reading, and production secret checks.
  - `test_worker.py`: the Redis queue on fakeredis (jobs survive a worker crash), the worker completing, retrying, and skipping deleted jobs through the real API, and webhook signatures.
- `services/notify`: signature verification and the event store with `node --test`.
- `apps/web/test`: the fetch client and the sign-in, list, detail, and expired-session flows with Vitest and Testing Library.

CI also runs `alembic upgrade head` and `alembic check` against a real PostgreSQL service.

## End to end

Needs Docker and the Playwright CLI (`npm install -g playwright`).

```bash
./scripts/e2e.sh
```

It starts the full compose stack and runs `e2e/ui.spec.ts` against http://localhost:3006: register, upload a file, wait for the worker, check the extract, confirm the signed webhook reached the receiver, and delete the job. A second test covers validation messages and pasted Spanish text.
