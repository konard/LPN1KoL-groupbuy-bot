use actix_web::{web, HttpResponse};
use sqlx::PgPool;

use crate::models::payment::*;

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
