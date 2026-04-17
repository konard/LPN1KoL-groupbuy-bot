use actix_web::{web, HttpResponse};
use rust_decimal::Decimal;
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

/// PUT/PATCH /api/procurements/{id}/
#[utoipa::path(
    put,
    path = "/api/procurements/{id}/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    request_body = UpdateProcurement,
    responses(
        (status = 200, description = "Procurement updated", body = ProcurementResponse),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn update_procurement(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<UpdateProcurement>,
) -> HttpResponse {
    let proc_id = path.into_inner();
    let data = body.into_inner();

    // Fetch existing
    let proc = match sqlx::query_as::<_, Procurement>("SELECT * FROM procurements WHERE id = $1")
        .bind(proc_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(p)) => p,
        Ok(None) => return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch procurement: {}", e);
            return HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}));
        }
    };

    let title = data.title.unwrap_or(proc.title);
    let description = data.description.unwrap_or(proc.description);
    let category_id = data.category_id.or(proc.category_id);
    let city = data.city.unwrap_or(proc.city);
    let delivery_address = data.delivery_address.unwrap_or(proc.delivery_address);
    let target_amount = data.target_amount.unwrap_or(proc.target_amount);
    let stop_at_amount = data.stop_at_amount.or(proc.stop_at_amount);
    let unit = data.unit.unwrap_or(proc.unit);
    let price_per_unit = data.price_per_unit.or(proc.price_per_unit);
    let commission_percent = data.commission_percent.unwrap_or(proc.commission_percent);
    let min_quantity = data.min_quantity.or(proc.min_quantity);
    let deadline = data.deadline.unwrap_or(proc.deadline);
    let payment_deadline = data.payment_deadline.or(proc.payment_deadline);
    let image_url = data.image_url.unwrap_or(proc.image_url);

    match sqlx::query_as::<_, Procurement>(
        r#"UPDATE procurements SET title=$1, description=$2, category_id=$3, city=$4,
            delivery_address=$5, target_amount=$6, stop_at_amount=$7, unit=$8, price_per_unit=$9,
            commission_percent=$10, min_quantity=$11, deadline=$12, payment_deadline=$13,
            image_url=$14, updated_at=NOW()
           WHERE id=$15 RETURNING *"#,
    )
    .bind(&title)
    .bind(&description)
    .bind(category_id)
    .bind(&city)
    .bind(&delivery_address)
    .bind(target_amount)
    .bind(stop_at_amount)
    .bind(&unit)
    .bind(price_per_unit)
    .bind(commission_percent)
    .bind(min_quantity)
    .bind(deadline)
    .bind(payment_deadline)
    .bind(&image_url)
    .bind(proc_id)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(updated) => {
            let count: i64 = sqlx::query_scalar(
                "SELECT COUNT(*) FROM participants WHERE procurement_id = $1 AND is_active = true",
            )
            .bind(proc_id)
            .fetch_one(pool.get_ref())
            .await
            .unwrap_or(0);
            HttpResponse::Ok().json(updated.to_response(count))
        }
        Err(e) => {
            tracing::error!("Failed to update procurement: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// DELETE /api/procurements/{id}/
#[utoipa::path(
    delete,
    path = "/api/procurements/{id}/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    responses(
        (status = 204, description = "Procurement deleted"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn delete_procurement(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let proc_id = path.into_inner();
    match sqlx::query("DELETE FROM procurements WHERE id = $1")
        .bind(proc_id)
        .execute(pool.get_ref())
        .await
    {
        Ok(result) if result.rows_affected() > 0 => HttpResponse::NoContent().finish(),
        Ok(_) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to delete procurement: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/procurements/{id}/participants/
#[utoipa::path(
    get,
    path = "/api/procurements/{id}/participants/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    responses(
        (status = 200, description = "List of participants", body = Vec<Participant>),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn list_participants(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let proc_id = path.into_inner();

    // Verify procurement exists
    let exists: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM procurements WHERE id = $1)")
        .bind(proc_id)
        .fetch_one(pool.get_ref())
        .await
        .unwrap_or(false);

    if !exists {
        return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."}));
    }

    match sqlx::query_as::<_, Participant>(
        "SELECT * FROM participants WHERE procurement_id = $1 AND is_active = true ORDER BY created_at ASC",
    )
    .bind(proc_id)
    .fetch_all(pool.get_ref())
    .await
    {
        Ok(participants) => HttpResponse::Ok().json(serde_json::json!({"results": participants})),
        Err(e) => {
            tracing::error!("Failed to fetch participants: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// POST /api/procurements/{id}/add_participant/
#[utoipa::path(
    post,
    path = "/api/procurements/{id}/add_participant/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    request_body = AddParticipantRequest,
    responses(
        (status = 201, description = "Participant added", body = Participant),
        (status = 400, description = "Bad request"),
        (status = 403, description = "Forbidden"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn add_participant(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<AddParticipantRequest>,
) -> HttpResponse {
    let proc_id = path.into_inner();
    let data = body.into_inner();

    let proc = match sqlx::query_as::<_, Procurement>("SELECT * FROM procurements WHERE id = $1")
        .bind(proc_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(p)) => p,
        Ok(None) => return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch procurement: {}", e);
            return HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}));
        }
    };

    if proc.organizer_id != data.organizer_id {
        return HttpResponse::Forbidden().json(serde_json::json!({"error": "Only the organizer can add participants"}));
    }

    let quantity = data.quantity.unwrap_or(Decimal::ONE);
    let notes = data.notes.unwrap_or_default();

    match sqlx::query_as::<_, Participant>(
        r#"INSERT INTO participants (procurement_id, user_id, quantity, amount, notes)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING *"#,
    )
    .bind(proc_id)
    .bind(data.user_id)
    .bind(quantity)
    .bind(data.amount)
    .bind(&notes)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(participant) => {
            let _ = sqlx::query(
                "UPDATE procurements SET current_amount = (SELECT COALESCE(SUM(amount), 0) FROM participants WHERE procurement_id = $1 AND is_active = true), updated_at = NOW() WHERE id = $1",
            )
            .bind(proc_id)
            .execute(pool.get_ref())
            .await;
            HttpResponse::Created().json(participant)
        }
        Err(e) => {
            tracing::error!("Failed to add participant: {}", e);
            HttpResponse::BadRequest().json(serde_json::json!({"error": format!("{}", e)}))
        }
    }
}

/// POST /api/procurements/{id}/check_access/
#[utoipa::path(
    post,
    path = "/api/procurements/{id}/check_access/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    request_body = CheckAccessRequest,
    responses(
        (status = 200, description = "Access check result"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn check_access(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<CheckAccessRequest>,
) -> HttpResponse {
    let proc_id = path.into_inner();
    let user_id = body.user_id;

    let proc = match sqlx::query_as::<_, Procurement>("SELECT * FROM procurements WHERE id = $1")
        .bind(proc_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(p)) => p,
        Ok(None) => return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch procurement: {}", e);
            return HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}));
        }
    };

    let is_organizer = proc.organizer_id == user_id;
    let is_participant: bool = sqlx::query_scalar(
        "SELECT EXISTS(SELECT 1 FROM participants WHERE procurement_id = $1 AND user_id = $2 AND is_active = true)",
    )
    .bind(proc_id)
    .bind(user_id)
    .fetch_one(pool.get_ref())
    .await
    .unwrap_or(false);

    let has_access = is_organizer || is_participant;
    HttpResponse::Ok().json(serde_json::json!({
        "has_access": has_access,
        "is_organizer": is_organizer,
        "is_participant": is_participant
    }))
}

/// POST /api/procurements/{id}/update_status/
#[utoipa::path(
    post,
    path = "/api/procurements/{id}/update_status/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    request_body = UpdateStatusRequest,
    responses(
        (status = 200, description = "Status updated", body = ProcurementResponse),
        (status = 400, description = "Bad request"),
        (status = 403, description = "Forbidden"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn update_status(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<UpdateStatusRequest>,
) -> HttpResponse {
    let proc_id = path.into_inner();
    let data = body.into_inner();

    let valid_statuses = ["draft", "active", "stopped", "payment", "completed", "cancelled"];
    if !valid_statuses.contains(&data.status.as_str()) {
        return HttpResponse::BadRequest().json(serde_json::json!({"error": "Invalid status"}));
    }

    let proc = match sqlx::query_as::<_, Procurement>("SELECT * FROM procurements WHERE id = $1")
        .bind(proc_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(p)) => p,
        Ok(None) => return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch procurement: {}", e);
            return HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}));
        }
    };

    if proc.organizer_id != data.organizer_id {
        return HttpResponse::Forbidden().json(serde_json::json!({"error": "Only the organizer can update status"}));
    }

    match sqlx::query_as::<_, Procurement>(
        "UPDATE procurements SET status=$1, updated_at=NOW() WHERE id=$2 RETURNING *",
    )
    .bind(&data.status)
    .bind(proc_id)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(updated) => {
            let count: i64 = sqlx::query_scalar(
                "SELECT COUNT(*) FROM participants WHERE procurement_id = $1 AND is_active = true",
            )
            .bind(proc_id)
            .fetch_one(pool.get_ref())
            .await
            .unwrap_or(0);
            HttpResponse::Ok().json(updated.to_response(count))
        }
        Err(e) => {
            tracing::error!("Failed to update status: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// POST /api/procurements/{id}/cast_vote/
#[utoipa::path(
    post,
    path = "/api/procurements/{id}/cast_vote/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    request_body = CastVoteRequest,
    responses(
        (status = 201, description = "Vote cast", body = Vote),
        (status = 400, description = "Bad request"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn cast_vote(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<CastVoteRequest>,
) -> HttpResponse {
    let proc_id = path.into_inner();
    let data = body.into_inner();

    // Verify procurement exists and is in valid state
    let proc = match sqlx::query_as::<_, Procurement>("SELECT * FROM procurements WHERE id = $1")
        .bind(proc_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(p)) => p,
        Ok(None) => return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch procurement: {}", e);
            return HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}));
        }
    };

    if proc.status != "active" && proc.status != "stopped" {
        return HttpResponse::BadRequest().json(serde_json::json!({"error": "Voting is only allowed when procurement is active or stopped"}));
    }

    let comment = data.comment.unwrap_or_default();

    match sqlx::query_as::<_, Vote>(
        r#"INSERT INTO procurement_votes (procurement_id, voter_id, supplier_id, comment)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (procurement_id, voter_id) DO UPDATE SET supplier_id=EXCLUDED.supplier_id, comment=EXCLUDED.comment
           RETURNING *"#,
    )
    .bind(proc_id)
    .bind(data.voter_id)
    .bind(data.supplier_id)
    .bind(&comment)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(vote) => HttpResponse::Created().json(vote),
        Err(e) => {
            tracing::error!("Failed to cast vote: {}", e);
            HttpResponse::BadRequest().json(serde_json::json!({"error": format!("{}", e)}))
        }
    }
}

/// GET /api/procurements/{id}/vote_results/
#[utoipa::path(
    get,
    path = "/api/procurements/{id}/vote_results/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    responses(
        (status = 200, description = "Vote results"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn vote_results(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let proc_id = path.into_inner();

    let exists: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM procurements WHERE id = $1)")
        .bind(proc_id)
        .fetch_one(pool.get_ref())
        .await
        .unwrap_or(false);

    if !exists {
        return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."}));
    }

    let total_votes: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM procurement_votes WHERE procurement_id = $1",
    )
    .bind(proc_id)
    .fetch_one(pool.get_ref())
    .await
    .unwrap_or(0);

    let rows = match sqlx::query_as::<_, (Uuid, i64)>(
        "SELECT supplier_id, COUNT(*) as vote_count FROM procurement_votes WHERE procurement_id = $1 GROUP BY supplier_id ORDER BY vote_count DESC",
    )
    .bind(proc_id)
    .fetch_all(pool.get_ref())
    .await
    {
        Ok(r) => r,
        Err(e) => {
            tracing::error!("Failed to fetch vote results: {}", e);
            return HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}));
        }
    };

    let results: Vec<VoteResult> = rows
        .into_iter()
        .map(|(supplier_id, vote_count)| VoteResult {
            supplier_id,
            vote_count,
            percentage: if total_votes > 0 { vote_count as f64 / total_votes as f64 * 100.0 } else { 0.0 },
            total_votes,
        })
        .collect();

    HttpResponse::Ok().json(serde_json::json!({
        "results": results,
        "total_votes": total_votes
    }))
}

/// POST /api/procurements/{id}/close_vote/
#[utoipa::path(
    post,
    path = "/api/procurements/{id}/close_vote/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    request_body = CloseVoteRequest,
    responses(
        (status = 200, description = "Vote close confirmation recorded"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn close_vote(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<CloseVoteRequest>,
) -> HttpResponse {
    let proc_id = path.into_inner();
    let user_id = body.user_id;

    let exists: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM procurements WHERE id = $1)")
        .bind(proc_id)
        .fetch_one(pool.get_ref())
        .await
        .unwrap_or(false);

    if !exists {
        return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."}));
    }

    let _ = sqlx::query(
        r#"INSERT INTO vote_close_confirmations (procurement_id, user_id)
           VALUES ($1, $2)
           ON CONFLICT (procurement_id, user_id) DO NOTHING"#,
    )
    .bind(proc_id)
    .bind(user_id)
    .execute(pool.get_ref())
    .await;

    let confirmed: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM vote_close_confirmations WHERE procurement_id = $1",
    )
    .bind(proc_id)
    .fetch_one(pool.get_ref())
    .await
    .unwrap_or(0);

    let total: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM participants WHERE procurement_id = $1 AND is_active = true",
    )
    .bind(proc_id)
    .fetch_one(pool.get_ref())
    .await
    .unwrap_or(0);

    HttpResponse::Ok().json(serde_json::json!({
        "confirmed": confirmed,
        "total": total,
        "user_id": user_id
    }))
}

/// GET /api/procurements/{id}/vote_close_status/
#[utoipa::path(
    get,
    path = "/api/procurements/{id}/vote_close_status/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    responses(
        (status = 200, description = "Vote close status"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn vote_close_status(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let proc_id = path.into_inner();

    let exists: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM procurements WHERE id = $1)")
        .bind(proc_id)
        .fetch_one(pool.get_ref())
        .await
        .unwrap_or(false);

    if !exists {
        return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."}));
    }

    let confirmed_users: Vec<Uuid> = sqlx::query_scalar(
        "SELECT user_id FROM vote_close_confirmations WHERE procurement_id = $1",
    )
    .bind(proc_id)
    .fetch_all(pool.get_ref())
    .await
    .unwrap_or_default();

    let total: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM participants WHERE procurement_id = $1 AND is_active = true",
    )
    .bind(proc_id)
    .fetch_one(pool.get_ref())
    .await
    .unwrap_or(0);

    HttpResponse::Ok().json(serde_json::json!({
        "confirmed_users": confirmed_users,
        "confirmed": confirmed_users.len() as i64,
        "total": total
    }))
}

/// POST /api/procurements/{id}/approve_supplier/
#[utoipa::path(
    post,
    path = "/api/procurements/{id}/approve_supplier/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    request_body = ApproveSupplierRequest,
    responses(
        (status = 200, description = "Supplier approved", body = ProcurementResponse),
        (status = 400, description = "Bad request"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn approve_supplier(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<ApproveSupplierRequest>,
) -> HttpResponse {
    let proc_id = path.into_inner();
    let supplier_id = body.supplier_id;

    match sqlx::query_as::<_, Procurement>(
        "UPDATE procurements SET supplier_id=$1, status='payment', updated_at=NOW() WHERE id=$2 RETURNING *",
    )
    .bind(supplier_id)
    .bind(proc_id)
    .fetch_optional(pool.get_ref())
    .await
    {
        Ok(Some(updated)) => {
            let count: i64 = sqlx::query_scalar(
                "SELECT COUNT(*) FROM participants WHERE procurement_id = $1 AND is_active = true",
            )
            .bind(proc_id)
            .fetch_one(pool.get_ref())
            .await
            .unwrap_or(0);
            HttpResponse::Ok().json(updated.to_response(count))
        }
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to approve supplier: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// POST /api/procurements/{id}/stop_amount/
#[utoipa::path(
    post,
    path = "/api/procurements/{id}/stop_amount/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    responses(
        (status = 200, description = "Procurement stopped for new participants"),
        (status = 400, description = "Bad request"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn stop_amount(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let proc_id = path.into_inner();

    let proc = match sqlx::query_as::<_, Procurement>("SELECT * FROM procurements WHERE id = $1")
        .bind(proc_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(p)) => p,
        Ok(None) => return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch procurement: {}", e);
            return HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}));
        }
    };

    if proc.status != "active" {
        return HttpResponse::BadRequest().json(serde_json::json!({"error": "Procurement must be active to stop amount"}));
    }

    let _ = sqlx::query(
        "UPDATE procurements SET status='stopped', updated_at=NOW() WHERE id=$1",
    )
    .bind(proc_id)
    .execute(pool.get_ref())
    .await;

    // Return confirmed participants
    let participants = sqlx::query_as::<_, Participant>(
        "SELECT * FROM participants WHERE procurement_id = $1 AND is_active = true ORDER BY created_at ASC",
    )
    .bind(proc_id)
    .fetch_all(pool.get_ref())
    .await
    .unwrap_or_default();

    HttpResponse::Ok().json(serde_json::json!({
        "message": "Procurement stopped for new participants",
        "participants": participants
    }))
}

/// GET /api/procurements/{id}/receipt_table/
#[utoipa::path(
    get,
    path = "/api/procurements/{id}/receipt_table/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    responses(
        (status = 200, description = "Receipt table", body = ReceiptTable),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn receipt_table(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let proc_id = path.into_inner();

    let proc = match sqlx::query_as::<_, Procurement>("SELECT * FROM procurements WHERE id = $1")
        .bind(proc_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(p)) => p,
        Ok(None) => return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch procurement: {}", e);
            return HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}));
        }
    };

    let participants = match sqlx::query_as::<_, Participant>(
        "SELECT * FROM participants WHERE procurement_id = $1 AND is_active = true AND status IN ('confirmed', 'paid') ORDER BY created_at ASC",
    )
    .bind(proc_id)
    .fetch_all(pool.get_ref())
    .await
    {
        Ok(p) => p,
        Err(e) => {
            tracing::error!("Failed to fetch participants: {}", e);
            return HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}));
        }
    };

    let rows: Vec<ReceiptRow> = participants
        .iter()
        .map(|p| ReceiptRow {
            user_id: p.user_id,
            quantity: p.quantity,
            amount: p.amount,
            notes: p.notes.clone(),
            status: p.status.clone(),
        })
        .collect();

    let total_amount: Decimal = participants.iter().map(|p| p.amount).sum();
    let commission_amount = total_amount * proc.commission_percent / Decimal::from(100);

    HttpResponse::Ok().json(ReceiptTable {
        rows,
        total_amount,
        commission_percent: proc.commission_percent,
        commission_amount,
    })
}

/// POST /api/procurements/{id}/close/
#[utoipa::path(
    post,
    path = "/api/procurements/{id}/close/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    responses(
        (status = 200, description = "Procurement closed", body = ProcurementResponse),
        (status = 400, description = "Bad request"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn close_procurement(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let proc_id = path.into_inner();

    let proc = match sqlx::query_as::<_, Procurement>("SELECT * FROM procurements WHERE id = $1")
        .bind(proc_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(p)) => p,
        Ok(None) => return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch procurement: {}", e);
            return HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}));
        }
    };

    if proc.status != "payment" && proc.status != "stopped" {
        return HttpResponse::BadRequest().json(serde_json::json!({"error": "Procurement must be in payment or stopped state to close"}));
    }

    match sqlx::query_as::<_, Procurement>(
        "UPDATE procurements SET status='completed', updated_at=NOW() WHERE id=$1 RETURNING *",
    )
    .bind(proc_id)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(updated) => {
            let count: i64 = sqlx::query_scalar(
                "SELECT COUNT(*) FROM participants WHERE procurement_id = $1 AND is_active = true",
            )
            .bind(proc_id)
            .fetch_one(pool.get_ref())
            .await
            .unwrap_or(0);
            HttpResponse::Ok().json(updated.to_response(count))
        }
        Err(e) => {
            tracing::error!("Failed to close procurement: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// POST /api/procurements/{id}/invite/
#[utoipa::path(
    post,
    path = "/api/procurements/{id}/invite/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    request_body = InviteRequest,
    responses(
        (status = 200, description = "Invitation sent"),
        (status = 403, description = "Forbidden"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn invite_user(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<InviteRequest>,
) -> HttpResponse {
    let proc_id = path.into_inner();
    let data = body.into_inner();

    let proc = match sqlx::query_as::<_, Procurement>("SELECT * FROM procurements WHERE id = $1")
        .bind(proc_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(p)) => p,
        Ok(None) => return HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch procurement: {}", e);
            return HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}));
        }
    };

    if proc.organizer_id != data.organizer_id {
        return HttpResponse::Forbidden().json(serde_json::json!({"error": "Only the organizer can invite users"}));
    }

    // Log the invitation (in production this would also send an email)
    let _ = sqlx::query(
        r#"INSERT INTO procurement_invitations (procurement_id, organizer_id, email)
           VALUES ($1, $2, $3)
           ON CONFLICT DO NOTHING"#,
    )
    .bind(proc_id)
    .bind(data.organizer_id)
    .bind(&data.email)
    .execute(pool.get_ref())
    .await;

    HttpResponse::Ok().json(serde_json::json!({
        "message": "Invitation sent",
        "email": data.email
    }))
}

/// POST /api/procurements/{id}/leave/
#[utoipa::path(
    post,
    path = "/api/procurements/{id}/leave/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Procurement ID")),
    request_body = LeaveProcurement,
    responses(
        (status = 200, description = "Left procurement"),
        (status = 404, description = "Procurement not found")
    )
)]
pub async fn leave_procurement(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<LeaveProcurement>,
) -> HttpResponse {
    let proc_id = path.into_inner();
    let user_id = body.user_id;

    match sqlx::query(
        "UPDATE participants SET is_active=false, updated_at=NOW() WHERE procurement_id=$1 AND user_id=$2 AND is_active=true",
    )
    .bind(proc_id)
    .bind(user_id)
    .execute(pool.get_ref())
    .await
    {
        Ok(result) if result.rows_affected() > 0 => {
            let _ = sqlx::query(
                "UPDATE procurements SET current_amount = (SELECT COALESCE(SUM(amount), 0) FROM participants WHERE procurement_id = $1 AND is_active = true), updated_at = NOW() WHERE id = $1",
            )
            .bind(proc_id)
            .execute(pool.get_ref())
            .await;
            HttpResponse::Ok().json(serde_json::json!({"message": "Left procurement", "procurement_id": proc_id}))
        }
        Ok(_) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not a participant."})),
        Err(e) => {
            tracing::error!("Failed to leave procurement: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// PATCH /api/procurements/participants/{id}/update_status/
#[utoipa::path(
    patch,
    path = "/api/procurements/participants/{id}/update_status/",
    tag = "procurements",
    params(("id" = i32, Path, description = "Participant ID")),
    request_body = UpdateParticipantStatusRequest,
    responses(
        (status = 200, description = "Participant status updated", body = Participant),
        (status = 400, description = "Invalid status"),
        (status = 404, description = "Participant not found")
    )
)]
pub async fn update_participant_status(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<UpdateParticipantStatusRequest>,
) -> HttpResponse {
    let participant_id = path.into_inner();
    let valid_statuses = ["pending", "confirmed", "paid", "completed", "cancelled"];
    if !valid_statuses.contains(&body.status.as_str()) {
        return HttpResponse::BadRequest().json(serde_json::json!({"error": "Invalid status"}));
    }

    match sqlx::query_as::<_, Participant>(
        "UPDATE participants SET status=$1, updated_at=NOW() WHERE id=$2 RETURNING *",
    )
    .bind(&body.status)
    .bind(participant_id)
    .fetch_optional(pool.get_ref())
    .await
    {
        Ok(Some(p)) => HttpResponse::Ok().json(p),
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to update participant status: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
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
