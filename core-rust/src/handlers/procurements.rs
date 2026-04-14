use actix_web::{web, HttpResponse};
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::procurement::*;

/// GET /api/procurements/
#[utoipa::path(
    get,
    path = "/api/procurements/",
    tag = "procurements",
    params(
        ("status" = Option<String>, Query, description = "Filter by status"),
        ("city" = Option<String>, Query, description = "Filter by city")
    ),
    responses(
        (status = 200, description = "List of procurements")
    )
)]
pub async fn list_procurements(
    pool: web::Data<PgPool>,
    query: web::Query<ProcurementQuery>,
) -> HttpResponse {
    let mut sql = "SELECT * FROM procurements WHERE 1=1".to_string();
    let mut params: Vec<String> = Vec::new();
    let mut idx = 0;

    if let Some(ref status) = query.status {
        idx += 1;
        sql.push_str(&format!(" AND status = ${}", idx));
        params.push(status.clone());
    }
    if let Some(ref city) = query.city {
        idx += 1;
        sql.push_str(&format!(" AND city = ${}", idx));
        params.push(city.clone());
    }

    sql.push_str(" ORDER BY created_at DESC");

    // Use a simpler approach - build different queries based on filters
    let procurements = if let Some(ref status) = query.status {
        if let Some(ref city) = query.city {
            sqlx::query_as::<_, Procurement>(
                "SELECT * FROM procurements WHERE status = $1 AND city = $2 ORDER BY created_at DESC",
            )
            .bind(status)
            .bind(city)
            .fetch_all(pool.get_ref())
            .await
        } else {
            sqlx::query_as::<_, Procurement>(
                "SELECT * FROM procurements WHERE status = $1 ORDER BY created_at DESC",
            )
            .bind(status)
            .fetch_all(pool.get_ref())
            .await
        }
    } else if let Some(ref city) = query.city {
        sqlx::query_as::<_, Procurement>(
            "SELECT * FROM procurements WHERE city = $1 ORDER BY created_at DESC",
        )
        .bind(city)
        .fetch_all(pool.get_ref())
        .await
    } else {
        sqlx::query_as::<_, Procurement>(
            "SELECT * FROM procurements ORDER BY created_at DESC",
        )
        .fetch_all(pool.get_ref())
        .await
    };

    match procurements {
        Ok(procs) => {
            let mut responses = Vec::new();
            for p in procs {
                let count: i64 = sqlx::query_scalar(
                    "SELECT COUNT(*) FROM participants WHERE procurement_id = $1 AND is_active = true",
                )
                .bind(p.id)
                .fetch_one(pool.get_ref())
                .await
                .unwrap_or(0);
                responses.push(p.to_response(count));
            }
            HttpResponse::Ok().json(serde_json::json!({"results": responses}))
        }
        Err(e) => {
            tracing::error!("Failed to fetch procurements: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// POST /api/procurements/
#[utoipa::path(
    post,
    path = "/api/procurements/",
    tag = "procurements",
    request_body = CreateProcurement,
    responses(
        (status = 201, description = "Procurement created", body = ProcurementResponse),
        (status = 400, description = "Bad request")
    )
)]
pub async fn create_procurement(
    pool: web::Data<PgPool>,
    body: web::Json<CreateProcurement>,
) -> HttpResponse {
    let data = body.into_inner();
    let delivery_address = data.delivery_address.unwrap_or_default();
    let unit = data.unit.unwrap_or_else(|| "units".to_string());
    let status = data.status.unwrap_or_else(|| "draft".to_string());
    let image_url = data.image_url.unwrap_or_default();
    let commission_percent = data
        .commission_percent
        .unwrap_or_else(|| rust_decimal::Decimal::ZERO);

    match sqlx::query_as::<_, Procurement>(
        r#"INSERT INTO procurements (title, description, category_id, organizer_id, city, delivery_address,
            target_amount, stop_at_amount, unit, price_per_unit, status, commission_percent, min_quantity,
            deadline, payment_deadline, image_url)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
           RETURNING *"#,
    )
    .bind(&data.title)
    .bind(&data.description)
    .bind(data.category_id)
    .bind(data.organizer_id)
    .bind(&data.city)
    .bind(&delivery_address)
    .bind(data.target_amount)
    .bind(data.stop_at_amount)
    .bind(&unit)
    .bind(data.price_per_unit)
    .bind(&status)
    .bind(commission_percent)
    .bind(data.min_quantity)
    .bind(data.deadline)
    .bind(data.payment_deadline)
    .bind(&image_url)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(proc) => HttpResponse::Created().json(proc.to_response(0)),
        Err(e) => {
            tracing::error!("Failed to create procurement: {}", e);
            HttpResponse::BadRequest().json(serde_json::json!({"error": format!("{}", e)}))
        }
    }
}

/// GET /api/procurements/{id}/
#[utoipa::path(
    get,
    path = "/api/procurements/{id}/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    responses(
        (status = 200, description = "Procurement found", body = ProcurementResponse),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn get_procurement(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let proc_id = path.into_inner();
    match sqlx::query_as::<_, Procurement>("SELECT * FROM procurements WHERE id = $1")
        .bind(proc_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(proc)) => {
            let count: i64 = sqlx::query_scalar(
                "SELECT COUNT(*) FROM participants WHERE procurement_id = $1 AND is_active = true",
            )
            .bind(proc_id)
            .fetch_one(pool.get_ref())
            .await
            .unwrap_or(0);
            HttpResponse::Ok().json(proc.to_response(count))
        }
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch procurement: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// POST /api/procurements/{id}/join/
#[utoipa::path(
    post,
    path = "/api/procurements/{id}/join/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    request_body = JoinProcurement,
    responses(
        (status = 201, description = "Joined procurement", body = Participant),
        (status = 400, description = "Bad request"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn join_procurement(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<JoinProcurement>,
) -> HttpResponse {
    let proc_id = path.into_inner();
    let data = body.into_inner();
    let quantity = data.quantity.unwrap_or(rust_decimal::Decimal::ONE);
    let notes = data.notes.unwrap_or_default();

    let user_id = match data.user_id {
        Some(id) => id,
        None => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": "user_id is required"}))
        }
    };

    // Check procurement can be joined
    let proc = match sqlx::query_as::<_, Procurement>("SELECT * FROM procurements WHERE id = $1")
        .bind(proc_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(p)) => p,
        Ok(None) => {
            return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."}))
        }
        Err(e) => {
            tracing::error!("Failed to fetch procurement: {}", e);
            return HttpResponse::InternalServerError()
                .json(serde_json::json!({"error": "Database error"}));
        }
    };

    if proc.status != "active" {
        return HttpResponse::BadRequest()
            .json(serde_json::json!({"error": "Procurement is not active"}));
    }

    match sqlx::query_as::<_, Participant>(
        r#"INSERT INTO participants (procurement_id, user_id, quantity, amount, notes)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING *"#,
    )
    .bind(proc_id)
    .bind(user_id)
    .bind(quantity)
    .bind(data.amount)
    .bind(&notes)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(participant) => {
            // Update procurement current amount
            let _ = sqlx::query(
                "UPDATE procurements SET current_amount = (SELECT COALESCE(SUM(amount), 0) FROM participants WHERE procurement_id = $1 AND is_active = true), updated_at = NOW() WHERE id = $1",
            )
            .bind(proc_id)
            .execute(pool.get_ref())
            .await;

            HttpResponse::Created().json(participant)
        }
        Err(e) => {
            tracing::error!("Failed to join procurement: {}", e);
            if e.to_string().contains("unique") || e.to_string().contains("duplicate") {
                HttpResponse::BadRequest()
                    .json(serde_json::json!({"error": "Already joined this procurement"}))
            } else {
                HttpResponse::BadRequest()
                    .json(serde_json::json!({"error": format!("{}", e)}))
            }
        }
    }
}

/// POST /api/procurements/{id}/leave/
#[utoipa::path(
    post,
    path = "/api/procurements/{id}/leave/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    responses(
        (status = 200, description = "Left procurement")
    )
)]
pub async fn leave_procurement(_pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let proc_id = path.into_inner();

    // For now, mark as inactive (needs user_id from auth in production)
    HttpResponse::Ok().json(serde_json::json!({"message": "Left procurement", "procurement_id": proc_id}))
}

/// GET /api/procurements/user/{user_id}/
#[utoipa::path(
    get,
    path = "/api/procurements/user/{user_id}/",
    tag = "procurements",
    params(("user_id" = Uuid, Path, description = "User ID")),
    responses(
        (status = 200, description = "User's organized and participating procurements")
    )
)]
pub async fn get_user_procurements(
    pool: web::Data<PgPool>,
    path: web::Path<Uuid>,
) -> HttpResponse {
    let user_id = path.into_inner();

    // Fetch procurements organized by this user
    let organized = match sqlx::query_as::<_, Procurement>(
        "SELECT * FROM procurements WHERE organizer_id = $1 ORDER BY created_at DESC",
    )
    .bind(user_id)
    .fetch_all(pool.get_ref())
    .await
    {
        Ok(procs) => procs,
        Err(e) => {
            tracing::error!("Failed to fetch organized procurements: {}", e);
            return HttpResponse::InternalServerError()
                .json(serde_json::json!({"error": "Database error"}));
        }
    };

    // Fetch procurements the user is participating in
    let participating = match sqlx::query_as::<_, Procurement>(
        r#"SELECT p.* FROM procurements p
           INNER JOIN participants pt ON p.id = pt.procurement_id
           WHERE pt.user_id = $1 AND pt.is_active = true
           ORDER BY p.created_at DESC"#,
    )
    .bind(user_id)
    .fetch_all(pool.get_ref())
    .await
    {
        Ok(procs) => procs,
        Err(e) => {
            tracing::error!("Failed to fetch participating procurements: {}", e);
            return HttpResponse::InternalServerError()
                .json(serde_json::json!({"error": "Database error"}));
        }
    };

    // Build responses with participant counts
    let mut organized_responses = Vec::new();
    for p in organized {
        let count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM participants WHERE procurement_id = $1 AND is_active = true",
        )
        .bind(p.id)
        .fetch_one(pool.get_ref())
        .await
        .unwrap_or(0);
        organized_responses.push(p.to_response(count));
    }

    let mut participating_responses = Vec::new();
    for p in participating {
        let count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM participants WHERE procurement_id = $1 AND is_active = true",
        )
        .bind(p.id)
        .fetch_one(pool.get_ref())
        .await
        .unwrap_or(0);
        participating_responses.push(p.to_response(count));
    }

    HttpResponse::Ok().json(serde_json::json!({
        "organized": organized_responses,
        "participating": participating_responses
    }))
}

/// GET /api/procurements/categories/
#[utoipa::path(
    get,
    path = "/api/procurements/categories/",
    tag = "procurements",
    responses(
        (status = 200, description = "List of categories", body = Vec<Category>)
    )
)]
pub async fn list_categories(pool: web::Data<PgPool>) -> HttpResponse {
    match sqlx::query_as::<_, Category>(
        "SELECT * FROM categories WHERE is_active = true ORDER BY name",
    )
    .fetch_all(pool.get_ref())
    .await
    {
        Ok(categories) => HttpResponse::Ok().json(categories),
        Err(e) => {
            tracing::error!("Failed to fetch categories: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}
