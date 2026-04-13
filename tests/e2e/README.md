# E2E Tests (Playwright)

Critical path tests for issue #282 requirements.

## Setup

```bash
cd tests/e2e
npm install
npx playwright install chromium
```

## Run

```bash
# Against a local dev server running at http://localhost:5173
BASE_URL=http://localhost:5173 npx playwright test

# Or with headed browser for debugging
npx playwright test --headed
```

## Test Files

| File | Scenario |
|------|----------|
| `ban-flow.spec.ts` | Scenario A: user_banned WebSocket event → forced logout → redirect /banned |
| `vote-flow.spec.ts` | Scenario C: vote button loading state, optimistic update, rollback on error |
| `message-flow.spec.ts` | Send photo message → verify display → soft delete |
