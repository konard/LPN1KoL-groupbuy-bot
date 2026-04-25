# Procurement Intelligence

The backend monolith exposes `GET /intelligence/purchases/{purchase_id}/report`
for organizer-facing operational decisions.

The report is built from a purchase snapshot and contains:

- collection progress, missing amount, daily velocity, and projected completion date;
- risk level with stable reason codes for dashboards and alerts;
- recommended actions for promotion, participant confirmation, payment collection,
  supplier approval, and delivery preparation;
- delivery batches grouped by participant city;
- weighted supplier vote leaderboard;
- notification audiences grouped by participant status.

The implementation keeps domain logic in `app.modules.intelligence.service` and
injects clock, risk, action, fulfillment, supplier scoring, and notification
planning policies. The FastAPI router and SQLAlchemy repository are adapters
around that service, so the decision logic can be tested without a database.
