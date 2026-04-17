use actix_web::{web, HttpResponse};
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::chat::*;

/// GET /api/chat/messages/unread_count/
#[utoipa::path(
    get,
    path = "/api/chat/messages/unread_count/",
    tag = "chat",
    params(
        ("user_id" = Uuid, Query, description = "User ID"),
        ("procurement_id" = Option<i32>, Query, description = "Filter by procurement ID")
    ),
    responses(
        (status = 200, description = "Unread message count"),
        (status = 400, description = "user_id is required")
    )
)]
pub async fn unread_count(
    pool: web::Data<PgPool>,
    query: web::Query<UnreadCountQuery>,
) -> HttpResponse {
    let user_id = query.user_id;

    if let Some(procurement_id) = query.procurement_id {
        let last_read: Option<i32> = sqlx::query_scalar(
            "SELECT last_read_message_id FROM message_reads WHERE user_id = $1 AND procurement_id = $2",
        )
        .bind(user_id)
        .bind(procurement_id)
        .fetch_optional(pool.get_ref())
        .await
        .unwrap_or(None)
        .flatten();

        let count: i64 = if let Some(last_id) = last_read {
            sqlx::query_scalar(
                "SELECT COUNT(*) FROM chat_messages WHERE procurement_id = $1 AND is_deleted = false AND id > $2",
            )
            .bind(procurement_id)
            .bind(last_id)
            .fetch_one(pool.get_ref())
            .await
            .unwrap_or(0)
        } else {
            sqlx::query_scalar(
                "SELECT COUNT(*) FROM chat_messages WHERE procurement_id = $1 AND is_deleted = false",
            )
            .bind(procurement_id)
            .fetch_one(pool.get_ref())
            .await
            .unwrap_or(0)
        };

        HttpResponse::Ok().json(serde_json::json!({
            "unread_count": count,
            "procurement_id": procurement_id
        }))
    } else {
        // Aggregate across all procurements user participates in
        let count: i64 = sqlx::query_scalar(
            r#"SELECT COUNT(*) FROM chat_messages cm
               WHERE cm.is_deleted = false
               AND cm.procurement_id IN (
                   SELECT procurement_id FROM participants WHERE user_id = $1 AND is_active = true
               )
               AND cm.id > COALESCE(
                   (SELECT last_read_message_id FROM message_reads mr
                    WHERE mr.user_id = $1 AND mr.procurement_id = cm.procurement_id),
                   0
               )"#,
        )
        .bind(user_id)
        .fetch_one(pool.get_ref())
        .await
        .unwrap_or(0);

        HttpResponse::Ok().json(serde_json::json!({"unread_count": count}))
    }
}

/// GET /api/chat/messages/?procurement=...
#[utoipa::path(
    get,
    path = "/api/chat/messages/",
    tag = "chat",
    params(
        ("procurement" = Option<i32>, Query, description = "Filter by procurement ID"),
        ("user" = Option<Uuid>, Query, description = "Filter by user ID")
    ),
    responses(
        (status = 200, description = "List of messages")
    )
)]
pub async fn list_messages(
    pool: web::Data<PgPool>,
    query: web::Query<MessageQuery>,
) -> HttpResponse {
    let messages = if let Some(procurement_id) = query.procurement {
        sqlx::query_as::<_, Message>(
            "SELECT * FROM chat_messages WHERE procurement_id = $1 AND is_deleted = false ORDER BY created_at ASC",
        )
        .bind(procurement_id)
        .fetch_all(pool.get_ref())
        .await
    } else {
        sqlx::query_as::<_, Message>(
            "SELECT * FROM chat_messages WHERE is_deleted = false ORDER BY created_at ASC LIMIT 100",
        )
        .fetch_all(pool.get_ref())
        .await
    };

    match messages {
        Ok(msgs) => HttpResponse::Ok().json(serde_json::json!({"results": msgs})),
        Err(e) => {
            tracing::error!("Failed to fetch messages: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// POST /api/chat/messages/
#[utoipa::path(
    post,
    path = "/api/chat/messages/",
    tag = "chat",
    request_body = CreateMessage,
    responses(
        (status = 201, description = "Message created", body = Message),
        (status = 400, description = "Bad request")
    )
)]
pub async fn create_message(
    pool: web::Data<PgPool>,
    body: web::Json<CreateMessage>,
) -> HttpResponse {
    let data = body.into_inner();
    let message_type = data.message_type.unwrap_or_else(|| "text".to_string());
    let attachment_url = data.attachment_url.unwrap_or_default();

    match sqlx::query_as::<_, Message>(
        r#"INSERT INTO chat_messages (procurement_id, user_id, message_type, text, attachment_url)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING *"#,
    )
    .bind(data.procurement)
    .bind(data.user)
    .bind(&message_type)
    .bind(&data.text)
    .bind(&attachment_url)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(message) => HttpResponse::Created().json(message),
        Err(e) => {
            tracing::error!("Failed to create message: {}", e);
            HttpResponse::BadRequest().json(serde_json::json!({"error": format!("{}", e)}))
        }
    }
}

/// POST /api/chat/messages/mark_read/
pub async fn mark_messages_read(
    pool: web::Data<PgPool>,
    body: web::Json<serde_json::Value>,
) -> HttpResponse {
    let user_id: Uuid = match body.get("user_id").and_then(|v| v.as_str()) {
        Some(s) => match Uuid::parse_str(s) {
            Ok(id) => id,
            Err(_) => {
                return HttpResponse::BadRequest()
                    .json(serde_json::json!({"error": "user_id must be a valid UUID"}))
            }
        },
        None => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": "user_id and procurement_id are required"}))
        }
    };
    let procurement_id = match body.get("procurement_id").and_then(|v| v.as_i64()) {
        Some(id) => id as i32,
        None => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": "user_id and procurement_id are required"}))
        }
    };
    let message_id = body.get("message_id").and_then(|v| v.as_i64()).map(|id| id as i32);

    // Determine the message_id to record (use provided or fetch last message)
    let effective_message_id = if let Some(mid) = message_id {
        Some(mid)
    } else {
        sqlx::query_scalar::<_, i32>(
            "SELECT id FROM chat_messages WHERE procurement_id = $1 AND is_deleted = false ORDER BY created_at DESC LIMIT 1",
        )
        .bind(procurement_id)
        .fetch_optional(pool.get_ref())
        .await
        .unwrap_or(None)
    };

    if let Some(mid) = effective_message_id {
        let _ = sqlx::query(
            r#"INSERT INTO message_reads (user_id, procurement_id, last_read_message_id)
               VALUES ($1, $2, $3)
               ON CONFLICT (user_id, procurement_id) DO UPDATE SET last_read_message_id = EXCLUDED.last_read_message_id"#,
        )
        .bind(user_id)
        .bind(procurement_id)
        .bind(mid)
        .execute(pool.get_ref())
        .await;
    }

    HttpResponse::Ok().json(serde_json::json!({"message": "Marked as read"}))
}

/// POST /api/chat/notifications/{id}/mark_read/
pub async fn mark_notification_read(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
) -> HttpResponse {
    let notification_id = path.into_inner();
    match sqlx::query_as::<_, Notification>(
        "UPDATE notifications SET is_read = true WHERE id = $1 RETURNING *",
    )
    .bind(notification_id)
    .fetch_optional(pool.get_ref())
    .await
    {
        Ok(Some(notif)) => HttpResponse::Ok().json(notif),
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to mark notification as read: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// POST /api/chat/notifications/
#[utoipa::path(
    post,
    path = "/api/chat/notifications/",
    tag = "chat",
    request_body = CreateNotification,
    responses(
        (status = 201, description = "Notification created", body = Notification),
        (status = 400, description = "Bad request")
    )
)]
pub async fn create_notification(
    pool: web::Data<PgPool>,
    body: web::Json<CreateNotification>,
) -> HttpResponse {
    let data = body.into_inner();

    match sqlx::query_as::<_, Notification>(
        r#"INSERT INTO notifications (user_id, notification_type, title, message, procurement_id)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING *"#,
    )
    .bind(data.user_id)
    .bind(&data.notification_type)
    .bind(&data.title)
    .bind(&data.message)
    .bind(data.procurement_id)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(notif) => HttpResponse::Created().json(notif),
        Err(e) => {
            tracing::error!("Failed to create notification: {}", e);
            HttpResponse::BadRequest().json(serde_json::json!({"error": format!("{}", e)}))
        }
    }
}

/// POST /api/chat/notifications/mark_all_read/
pub async fn mark_all_notifications_read(
    pool: web::Data<PgPool>,
    body: web::Json<MarkAllReadRequest>,
) -> HttpResponse {
    let user_id = body.user_id;

    match sqlx::query_scalar::<_, i64>(
        "WITH updated AS (UPDATE notifications SET is_read=true WHERE user_id=$1 AND is_read=false RETURNING id) SELECT COUNT(*) FROM updated",
    )
    .bind(user_id)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(count) => HttpResponse::Ok().json(serde_json::json!({"updated": count})),
        Err(e) => {
            tracing::error!("Failed to mark all notifications as read: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/chat/notifications/?user_id=...
#[utoipa::path(
    get,
    path = "/api/chat/notifications/",
    tag = "chat",
    params(("user_id" = Option<Uuid>, Query, description = "Filter by user ID")),
    responses(
        (status = 200, description = "List of notifications", body = Vec<Notification>)
    )
)]
pub async fn list_notifications(
    pool: web::Data<PgPool>,
    query: web::Query<NotificationQuery>,
) -> HttpResponse {
    let notifications = if let Some(user_id) = query.user_id {
        sqlx::query_as::<_, Notification>(
            "SELECT * FROM notifications WHERE user_id = $1 ORDER BY created_at DESC",
        )
        .bind(user_id)
        .fetch_all(pool.get_ref())
        .await
    } else {
        sqlx::query_as::<_, Notification>(
            "SELECT * FROM notifications ORDER BY created_at DESC LIMIT 100",
        )
        .fetch_all(pool.get_ref())
        .await
    };

    match notifications {
        Ok(notifs) => HttpResponse::Ok().json(notifs),
        Err(e) => {
            tracing::error!("Failed to fetch notifications: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}
