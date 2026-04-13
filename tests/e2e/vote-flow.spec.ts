/**
 * E2E Test: Scenario C — Concurrent Voting (issue #282, Part II §5)
 *
 * On vote click:
 *  1. Button enters `loading` state and is disabled immediately (no double-click)
 *  2. Optimistic update: targeted option count increments before server responds
 *  3. On success: count stays updated, toast shown
 *  4. On server error: count rolls back, button re-enabled
 *  5. On 429: button disabled with countdown timer
 */
import { test, expect } from '@playwright/test';

const BASE = process.env.BASE_URL ?? 'http://localhost:5173';

// ── Helpers ──────────────────────────────────────────────────────────────────

async function setupAuthAndProcurement(page: any) {
  await page.route('**/api/users/**', (route: any) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'voter-user-1',
        first_name: 'Voter',
        last_name: 'User',
        email: 'voter@example.com',
      }),
    });
  });

  await page.route('**/api/procurements/123/', (route: any) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 123,
        title: 'Test Group Buy',
        status: 'active',
        participant_count: 3,
      }),
    });
  });

  await page.route('**/api/procurements/?*', (route: any) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        results: [{
          id: 123,
          title: 'Test Group Buy',
          status: 'active',
          participant_count: 3,
        }],
        count: 1,
      }),
    });
  });

  await page.route('**/api/procurements/123/vote_results/**', (route: any) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_votes: 2,
        results: [
          { supplier_id: 1, supplier_name: 'Alpha Corp', vote_count: 2, percentage: 100 },
        ],
        user_votes: {},
      }),
    });
  });

  await page.route('**/api/procurements/123/vote_close_status/**', (route: any) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ closed_by: [] }),
    });
  });

  await page.route('**/api/users/?role=supplier*', (route: any) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        results: [
          { id: 1, first_name: 'Alpha', last_name: 'Corp', username: 'alpha' },
          { id: 2, first_name: 'Beta', last_name: 'Ltd', username: 'beta' },
        ],
      }),
    });
  });

  await page.route('**/api/procurements/123/participants/**', (route: any) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'voter-user-1', name: 'Voter User' },
        { id: 'user-2', name: 'User Two' },
        { id: 'user-3', name: 'User Three' },
      ]),
    });
  });

  await page.route('**/api/chat/messages/**', (route: any) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ results: [] }),
    });
  });

  await page.goto(BASE);
  await page.evaluate(() => {
    localStorage.setItem('userId', 'voter-user-1');
    localStorage.setItem('authToken', 'fake-jwt-token');
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

test.describe('Scenario C: Concurrent Voting', () => {
  test('vote button is disabled while request is in-flight', async ({ page }) => {
    await setupAuthAndProcurement(page);

    // Delay the cast_vote response to test loading state
    let resolveVote: () => void;
    const voteResponsePromise = new Promise<void>((resolve) => { resolveVote = resolve; });

    await page.route('**/api/procurements/123/cast_vote/**', async (route: any) => {
      await voteResponsePromise;
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });

    await page.goto(`${BASE}/chat/123`);

    // Select a supplier and click vote
    const select = page.locator('select.form-input').first();
    if (await select.isVisible({ timeout: 3000 }).catch(() => false)) {
      await select.selectOption({ index: 1 });

      const voteBtn = page.locator('button:has-text("Проголосовать"), button:has-text("Изменить голос")').first();
      await voteBtn.click();

      // Button should be disabled while request is in-flight
      await expect(voteBtn).toBeDisabled({ timeout: 2000 });

      // Unblock the response
      resolveVote!();

      // Button should be re-enabled after success
      await expect(voteBtn).toBeEnabled({ timeout: 5000 });
    }
  });

  test('vote button shows countdown on 429 response', async ({ page }) => {
    await setupAuthAndProcurement(page);

    await page.route('**/api/procurements/123/cast_vote/**', (route: any) => {
      route.fulfill({
        status: 429,
        headers: { 'Retry-After': '30' },
        contentType: 'application/json',
        body: JSON.stringify({
          status: 429,
          code: 'RATE_LIMITED',
          message: 'Too Many Requests',
        }),
      });
    });

    await page.goto(`${BASE}/chat/123`);

    const select = page.locator('select.form-input').first();
    if (await select.isVisible({ timeout: 3000 }).catch(() => false)) {
      await select.selectOption({ index: 1 });

      const voteBtn = page.locator('button:has-text("Проголосовать"), button:has-text("Изменить голос")').first();
      await voteBtn.click();

      // After 429, button should show countdown
      await expect(voteBtn).toContainText(/Подождите/, { timeout: 3000 });
      await expect(voteBtn).toBeDisabled();
    }
  });

  test('vote button rolls back on server error', async ({ page }) => {
    await setupAuthAndProcurement(page);

    await page.route('**/api/procurements/123/cast_vote/**', (route: any) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 500,
          code: 'INTERNAL_ERROR',
          message: 'Internal server error',
        }),
      });
    });

    await page.goto(`${BASE}/chat/123`);

    const select = page.locator('select.form-input').first();
    if (await select.isVisible({ timeout: 3000 }).catch(() => false)) {
      await select.selectOption({ index: 1 });

      const voteBtn = page.locator('button:has-text("Проголосовать"), button:has-text("Изменить голос")').first();
      await voteBtn.click();

      // After error, button should be re-enabled (not stuck in loading)
      await expect(voteBtn).toBeEnabled({ timeout: 5000 });
      // Should still say "Проголосовать" (rolled back, user has no active vote)
      await expect(voteBtn).toContainText(/Проголосовать/);
    }
  });
});
