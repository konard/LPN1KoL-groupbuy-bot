use actix_web::{web, HttpResponse};
use rust_decimal::Decimal;
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::payment::*;

/// GET /api/payments/
#[utoipa::path(
    get,
    path = "/api/payments/",
    tag = "payments",
    params(
        ("user_id" = Option<Uuid>, Query, description = "Filter by user ID"),
        ("payment_type" = Option<String>, Query, description = "Filter by payment type"),
        ("status" = Option<String>, Query, description = "Filter by status")
    ),
    responses(
        (status = 200, description = "List of payments")
    )
)]
pub async fn list_payments(
    pool: web::Data<PgPool>,
    query: web::Query<PaymentQuery>,
) -> HttpResponse {
    let payments = match (&query.user_id, &query.payment_type, &query.status) {
        (Some(uid), Some(pt), Some(st)) => {
            sqlx::query_as::<_, Payment>(
                "SELECT * FROM payments WHERE user_id=$1 AND payment_type=$2 AND status=$3 ORDER BY created_at DESC",
            )
            .bind(uid)
            .bind(pt)
            .bind(st)
            .fetch_all(pool.get_ref())
            .await
        }
        (Some(uid), Some(pt), None) => {
            sqlx::query_as::<_, Payment>(
                "SELECT * FROM payments WHERE user_id=$1 AND payment_type=$2 ORDER BY created_at DESC",
            )
            .bind(uid)
            .bind(pt)
            .fetch_all(pool.get_ref())
            .await
        }
        (Some(uid), None, Some(st)) => {
            sqlx::query_as::<_, Payment>(
                "SELECT * FROM payments WHERE user_id=$1 AND status=$2 ORDER BY created_at DESC",
            )
            .bind(uid)
            .bind(st)
            .fetch_all(pool.get_ref())
            .await
        }
        (Some(uid), None, None) => {
            sqlx::query_as::<_, Payment>(
                "SELECT * FROM payments WHERE user_id=$1 ORDER BY created_at DESC",
            )
            .bind(uid)
            .fetch_all(pool.get_ref())
            .await
        }
        (None, Some(pt), Some(st)) => {
            sqlx::query_as::<_, Payment>(
                "SELECT * FROM payments WHERE payment_type=$1 AND status=$2 ORDER BY created_at DESC",
            )
            .bind(pt)
            .bind(st)
            .fetch_all(pool.get_ref())
            .await
        }
        (None, Some(pt), None) => {
            sqlx::query_as::<_, Payment>(
                "SELECT * FROM payments WHERE payment_type=$1 ORDER BY created_at DESC",
            )
            .bind(pt)
            .fetch_all(pool.get_ref())
            .await
        }
        (None, None, Some(st)) => {
            sqlx::query_as::<_, Payment>(
                "SELECT * FROM payments WHERE status=$1 ORDER BY created_at DESC",
            )
            .bind(st)
            .fetch_all(pool.get_ref())
            .await
        }
        (None, None, None) => {
            sqlx::query_as::<_, Payment>(
                "SELECT * FROM payments ORDER BY created_at DESC LIMIT 100",
            )
            .fetch_all(pool.get_ref())
            .await
        }
    };

    match payments {
        Ok(p) => HttpResponse::Ok().json(serde_json::json!({"results": p})),
        Err(e) => {
            tracing::error!("Failed to fetch payments: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/payments/{id}/
#[utoipa::path(
    get,
    path = "/api/payments/{id}/",
    tag = "payments",
    params(("id" = i32, Path, description = "Payment ID")),
    responses(
        (status = 200, description = "Payment details", body = Payment),
        (status = 404, description = "Payment not found")
    )
)]
pub async fn get_payment(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let payment_id = path.into_inner();
    match sqlx::query_as::<_, Payment>("SELECT * FROM payments WHERE id = $1")
        .bind(payment_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(p)) => HttpResponse::Ok().json(p),
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch payment: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// POST /api/payments/{id}/simulate_success/
#[utoipa::path(
    post,
    path = "/api/payments/{id}/simulate_success/",
    tag = "payments",
    params(("id" = i32, Path, description = "Payment ID")),
    responses(
        (status = 200, description = "Payment simulated as successful"),
        (status = 404, description = "Payment not found")
    )
)]
pub async fn simulate_success(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let payment_id = path.into_inner();

    let payment = match sqlx::query_as::<_, Payment>("SELECT * FROM payments WHERE id = $1")
        .bind(payment_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(p)) => p,
        Ok(None) => return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch payment: {}", e);
            return HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}));
        }
    };

    // Mark payment as succeeded
    let _ = sqlx::query(
        "UPDATE payments SET status='succeeded', paid_at=NOW(), updated_at=NOW() WHERE id=$1",
    )
    .bind(payment_id)
    .execute(pool.get_ref())
    .await;

    // Update user balance
    let _ = sqlx::query(
        "UPDATE users SET balance = balance + $1, updated_at=NOW() WHERE id = $2",
    )
    .bind(payment.amount)
    .bind(payment.user_id)
    .execute(pool.get_ref())
    .await;

    // Record transaction
    let new_balance: Decimal = sqlx::query_scalar("SELECT balance FROM users WHERE id = $1")
        .bind(payment.user_id)
        .fetch_one(pool.get_ref())
        .await
        .unwrap_or(Decimal::ZERO);

    let _ = sqlx::query(
        r#"INSERT INTO transactions (user_id, transaction_type, amount, balance_after, payment_id, description)
           VALUES ($1, 'deposit', $2, $3, $4, 'Payment simulation')"#,
    )
    .bind(payment.user_id)
    .bind(payment.amount)
    .bind(new_balance)
    .bind(payment_id)
    .execute(pool.get_ref())
    .await;

    HttpResponse::Ok().json(serde_json::json!({"status": "succeeded", "payment_id": payment_id}))
}

/// GET /api/payments/transactions/
#[utoipa::path(
    get,
    path = "/api/payments/transactions/",
    tag = "payments",
    params(
        ("user_id" = Option<Uuid>, Query, description = "Filter by user ID"),
        ("transaction_type" = Option<String>, Query, description = "Filter by transaction type")
    ),
    responses(
        (status = 200, description = "List of transactions")
    )
)]
pub async fn list_transactions(
    pool: web::Data<PgPool>,
    query: web::Query<TransactionQuery>,
) -> HttpResponse {
    let transactions = match (&query.user_id, &query.transaction_type) {
        (Some(uid), Some(tt)) => {
            sqlx::query_as::<_, Transaction>(
                "SELECT * FROM transactions WHERE user_id=$1 AND transaction_type=$2 ORDER BY created_at DESC",
            )
            .bind(uid)
            .bind(tt)
            .fetch_all(pool.get_ref())
            .await
        }
        (Some(uid), None) => {
            sqlx::query_as::<_, Transaction>(
                "SELECT * FROM transactions WHERE user_id=$1 ORDER BY created_at DESC",
            )
            .bind(uid)
            .fetch_all(pool.get_ref())
            .await
        }
        (None, Some(tt)) => {
            sqlx::query_as::<_, Transaction>(
                "SELECT * FROM transactions WHERE transaction_type=$1 ORDER BY created_at DESC",
            )
            .bind(tt)
            .fetch_all(pool.get_ref())
            .await
        }
        (None, None) => {
            sqlx::query_as::<_, Transaction>(
                "SELECT * FROM transactions ORDER BY created_at DESC LIMIT 100",
            )
            .fetch_all(pool.get_ref())
            .await
        }
    };

    match transactions {
        Ok(t) => HttpResponse::Ok().json(serde_json::json!({"results": t})),
        Err(e) => {
            tracing::error!("Failed to fetch transactions: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/payments/transactions/{id}/
#[utoipa::path(
    get,
    path = "/api/payments/transactions/{id}/",
    tag = "payments",
    params(("id" = i32, Path, description = "Transaction ID")),
    responses(
        (status = 200, description = "Transaction details", body = Transaction),
        (status = 404, description = "Transaction not found")
    )
)]
pub async fn get_transaction(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let tx_id = path.into_inner();
    match sqlx::query_as::<_, Transaction>("SELECT * FROM transactions WHERE id = $1")
        .bind(tx_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(t)) => HttpResponse::Ok().json(t),
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch transaction: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/payments/transactions/summary/
#[utoipa::path(
    get,
    path = "/api/payments/transactions/summary/",
    tag = "payments",
    params(("user_id" = Uuid, Query, description = "User ID")),
    responses(
        (status = 200, description = "Transaction summary", body = TransactionSummary),
        (status = 400, description = "user_id is required")
    )
)]
pub async fn transaction_summary(
    pool: web::Data<PgPool>,
    query: web::Query<std::collections::HashMap<String, String>>,
) -> HttpResponse {
    let user_id = match query.get("user_id").and_then(|s| Uuid::parse_str(s).ok()) {
        Some(id) => id,
        None => return HttpResponse::BadRequest().json(serde_json::json!({"error": "user_id is required"})),
    };

    let current_balance: Decimal = sqlx::query_scalar("SELECT balance FROM users WHERE id = $1")
        .bind(user_id)
        .fetch_optional(pool.get_ref())
        .await
        .unwrap_or(None)
        .unwrap_or(Decimal::ZERO);

    let total_deposited: Decimal = sqlx::query_scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=$1 AND transaction_type='deposit'",
    )
    .bind(user_id)
    .fetch_one(pool.get_ref())
    .await
    .unwrap_or(Decimal::ZERO);

    let total_withdrawn: Decimal = sqlx::query_scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=$1 AND transaction_type='withdrawal'",
    )
    .bind(user_id)
    .fetch_one(pool.get_ref())
    .await
    .unwrap_or(Decimal::ZERO);

    let total_refunded: Decimal = sqlx::query_scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=$1 AND transaction_type='refund'",
    )
    .bind(user_id)
    .fetch_one(pool.get_ref())
    .await
    .unwrap_or(Decimal::ZERO);

    let transaction_count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM transactions WHERE user_id=$1",
    )
    .bind(user_id)
    .fetch_one(pool.get_ref())
    .await
    .unwrap_or(0);

    HttpResponse::Ok().json(TransactionSummary {
        current_balance,
        total_deposited,
        total_withdrawn,
        total_refunded,
        transaction_count,
    })
}

/// POST /api/payments/webhook/
pub async fn payment_webhook(body: web::Bytes) -> HttpResponse {
    // Auto-detect provider from payload structure and route accordingly
    let payload = match serde_json::from_slice::<serde_json::Value>(&body) {
        Ok(v) => v,
        Err(_) => return HttpResponse::BadRequest().json(serde_json::json!({"error": "Invalid JSON"})),
    };

    // Detect provider: Tochka uses "event" field with "payment." prefix; YooKassa uses "type" field
    let is_tochka = payload.get("event").is_some();
    let provider = if is_tochka { "tochka" } else { "yookassa" };

    tracing::info!("Received payment webhook from provider: {}", provider);

    // In production this would verify webhook signatures and update payment status
    HttpResponse::Ok().json(serde_json::json!({"received": true, "provider": provider}))
}

/// POST /api/payments/
#[utoipa::path(
    post,
    path = "/api/payments/",
    tag = "payments",
    request_body = CreatePayment,
    responses(
        (status = 201, description = "Payment created", body = Payment),
        (status = 400, description = "Bad request")
    )
)]
pub async fn create_payment(
    pool: web::Data<PgPool>,
    body: web::Json<CreatePayment>,
) -> HttpResponse {
    let data = body.into_inner();
    let description = data.description.unwrap_or_default();

    match sqlx::query_as::<_, Payment>(
        r#"INSERT INTO payments (user_id, payment_type, amount, procurement_id, description)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING *"#,
    )
    .bind(data.user_id)
    .bind(&data.payment_type)
    .bind(data.amount)
    .bind(data.procurement_id)
    .bind(&description)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(payment) => HttpResponse::Created().json(payment),
        Err(e) => {
            tracing::error!("Failed to create payment: {}", e);
            HttpResponse::BadRequest().json(serde_json::json!({"error": format!("{}", e)}))
        }
    }
}

/// GET /api/payments/{id}/status/
#[utoipa::path(
    get,
    path = "/api/payments/{id}/status/",
    tag = "payments",
    params(("id" = i32, Path, description = "Payment ID")),
    responses(
        (status = 200, description = "Payment status", body = PaymentStatusResponse),
        (status = 404, description = "Payment not found")
    )
)]
pub async fn get_payment_status(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let payment_id = path.into_inner();
    match sqlx::query_as::<_, Payment>("SELECT * FROM payments WHERE id = $1")
        .bind(payment_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(payment)) => {
            let status_display = match payment.status.as_str() {
                "pending" => "Pending",
                "waiting_for_capture" => "Waiting for Capture",
                "succeeded" => "Succeeded",
                "cancelled" => "Cancelled",
                "refunded" => "Refunded",
                other => other,
            }
            .to_string();

            HttpResponse::Ok().json(PaymentStatusResponse {
                id: payment.id,
                status: payment.status,
                status_display,
                amount: payment.amount,
                confirmation_url: payment.confirmation_url,
            })
        }
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch payment: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}
