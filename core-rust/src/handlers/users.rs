use actix_web::{web, HttpResponse};
use jsonwebtoken::{encode, EncodingKey, Header};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use sqlx::PgPool;

use crate::models::user::*;

const WS_TOKEN_TTL_SECS: u64 = 86400; // 24 hours

#[derive(Debug, Serialize, Deserialize)]
struct WsClaims {
    user_id: i32,
    iat: u64,
    exp: u64,
}

/// GET /api/users/
#[utoipa::path(
    get,
    path = "/api/users/",
    tag = "users",
    responses(
        (status = 200, description = "List of users", body = Vec<UserResponse>)
    )
)]
pub async fn list_users(pool: web::Data<PgPool>) -> HttpResponse {
    match sqlx::query_as::<_, User>("SELECT * FROM users ORDER BY created_at DESC")
        .fetch_all(pool.get_ref())
        .await
    {
        Ok(users) => {
            let responses: Vec<UserResponse> = users.into_iter().map(UserResponse::from).collect();
            HttpResponse::Ok().json(responses)
        }
        Err(e) => {
            tracing::error!("Failed to fetch users: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// POST /api/users/
#[utoipa::path(
    post,
    path = "/api/users/",
    tag = "users",
    request_body = CreateUser,
    responses(
        (status = 201, description = "User created", body = UserResponse),
        (status = 400, description = "Bad request")
    )
)]
pub async fn create_user(pool: web::Data<PgPool>, body: web::Json<CreateUser>) -> HttpResponse {
    let data = body.into_inner();

    if data.platform_user_id.is_empty() {
        return HttpResponse::BadRequest()
            .json(serde_json::json!({"platform_user_id": ["Обязательное поле."]}));
    }

    let platform = data.platform.unwrap_or_else(|| "telegram".to_string());
    let username = data.username.unwrap_or_default();
    let first_name = data.first_name.unwrap_or_default();
    let last_name = data.last_name.unwrap_or_default();
    let phone = data.phone.unwrap_or_default();
    let email = data.email.unwrap_or_default();
    let role = data.role.unwrap_or_else(|| "buyer".to_string());
    let language_code = data.language_code.unwrap_or_else(|| "ru".to_string());
    let selfie_file_id = data.selfie_file_id.unwrap_or_default();

    // Truncate fields to their column limits to avoid "value too long" errors
    let platform = truncate_str(&platform, 20);
    let role = truncate_str(&role, 20);
    let language_code = truncate_str(&language_code, 20);
    let phone = truncate_str(&phone, 30);

    // Normalize phone: ensure it starts with + if non-empty
    let phone = if !phone.is_empty() && !phone.starts_with('+') {
        format!("+{}", phone)
    } else {
        phone.to_string()
    };

    match sqlx::query_as::<_, User>(
        r#"INSERT INTO users (platform, platform_user_id, username, first_name, last_name, phone, email, role, language_code, selfie_file_id, is_banned)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, false)
           RETURNING *"#,
    )
    .bind(&platform)
    .bind(&data.platform_user_id)
    .bind(&username)
    .bind(&first_name)
    .bind(&last_name)
    .bind(&phone)
    .bind(&email)
    .bind(&role)
    .bind(&language_code)
    .bind(&selfie_file_id)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(user) => HttpResponse::Created().json(UserResponse::from(user)),
        Err(e) => {
            tracing::error!("Failed to create user: {}", e);
            if e.to_string().contains("unique") || e.to_string().contains("duplicate") {
                HttpResponse::BadRequest()
                    .json(serde_json::json!({"error": "User with this platform and platform_user_id already exists"}))
            } else {
                HttpResponse::BadRequest()
                    .json(serde_json::json!({"error": format!("{}", e)}))
            }
        }
    }
}

/// Truncate a string to at most `max_chars` Unicode scalar values.
fn truncate_str(s: &str, max_chars: usize) -> String {
    if s.chars().count() <= max_chars {
        s.to_string()
    } else {
        s.chars().take(max_chars).collect()
    }
}

/// GET /api/users/{id}/
#[utoipa::path(
    get,
    path = "/api/users/{id}/",
    tag = "users",
    params(("id" = i32, Path, description = "User ID")),
    responses(
        (status = 200, description = "User found", body = UserResponse),
        (status = 404, description = "User not found")
    )
)]
pub async fn get_user(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let user_id = path.into_inner();
    match sqlx::query_as::<_, User>("SELECT * FROM users WHERE id = $1")
        .bind(user_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(user)) => HttpResponse::Ok().json(UserResponse::from(user)),
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch user: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// PATCH /api/users/{id}/
#[utoipa::path(
    patch,
    path = "/api/users/{id}/",
    tag = "users",
    params(("id" = i32, Path, description = "User ID")),
    request_body = UpdateUser,
    responses(
        (status = 200, description = "User updated", body = UserResponse),
        (status = 404, description = "User not found")
    )
)]
pub async fn update_user(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<UpdateUser>,
) -> HttpResponse {
    let user_id = path.into_inner();
    let data = body.into_inner();

    // Build dynamic update query
    let mut updates = Vec::new();
    let mut param_idx = 1;

    if data.first_name.is_some() {
        param_idx += 1;
        updates.push(format!("first_name = ${}", param_idx));
    }
    if data.last_name.is_some() {
        param_idx += 1;
        updates.push(format!("last_name = ${}", param_idx));
    }
    if data.phone.is_some() {
        param_idx += 1;
        updates.push(format!("phone = ${}", param_idx));
    }
    if data.email.is_some() {
        param_idx += 1;
        updates.push(format!("email = ${}", param_idx));
    }
    if data.role.is_some() {
        param_idx += 1;
        updates.push(format!("role = ${}", param_idx));
    }

    if updates.is_empty() {
        return match sqlx::query_as::<_, User>("SELECT * FROM users WHERE id = $1")
            .bind(user_id)
            .fetch_optional(pool.get_ref())
            .await
        {
            Ok(Some(user)) => HttpResponse::Ok().json(UserResponse::from(user)),
            Ok(None) => {
                HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."}))
            }
            Err(e) => {
                tracing::error!("Failed to fetch user: {}", e);
                HttpResponse::InternalServerError()
                    .json(serde_json::json!({"error": "Database error"}))
            }
        };
    }

    updates.push("updated_at = NOW()".to_string());
    let query = format!(
        "UPDATE users SET {} WHERE id = $1 RETURNING *",
        updates.join(", ")
    );

    let mut q = sqlx::query_as::<_, User>(&query).bind(user_id);

    if let Some(ref v) = data.first_name {
        q = q.bind(v);
    }
    if let Some(ref v) = data.last_name {
        q = q.bind(v);
    }
    if let Some(ref v) = data.phone {
        q = q.bind(v);
    }
    if let Some(ref v) = data.email {
        q = q.bind(v);
    }
    if let Some(ref v) = data.role {
        q = q.bind(v);
    }

    match q.fetch_optional(pool.get_ref()).await {
        Ok(Some(user)) => HttpResponse::Ok().json(UserResponse::from(user)),
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to update user: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// DELETE /api/users/{id}/
#[utoipa::path(
    delete,
    path = "/api/users/{id}/",
    tag = "users",
    params(("id" = i32, Path, description = "User ID")),
    responses(
        (status = 204, description = "User deleted"),
        (status = 404, description = "User not found")
    )
)]
pub async fn delete_user(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let user_id = path.into_inner();
    match sqlx::query("DELETE FROM users WHERE id = $1")
        .bind(user_id)
        .execute(pool.get_ref())
        .await
    {
        Ok(result) => {
            if result.rows_affected() > 0 {
                HttpResponse::NoContent().finish()
            } else {
                HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."}))
            }
        }
        Err(e) => {
            tracing::error!("Failed to delete user: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/users/by_platform/?platform=...&platform_user_id=...
#[utoipa::path(
    get,
    path = "/api/users/by_platform/",
    tag = "users",
    params(
        ("platform" = Option<String>, Query, description = "Platform name"),
        ("platform_user_id" = String, Query, description = "Platform user ID")
    ),
    responses(
        (status = 200, description = "User found", body = UserResponse),
        (status = 404, description = "User not found")
    )
)]
pub async fn get_user_by_platform(
    pool: web::Data<PgPool>,
    query: web::Query<PlatformQuery>,
) -> HttpResponse {
    let platform = query.platform.clone().unwrap_or_else(|| "telegram".to_string());
    let platform_user_id = match &query.platform_user_id {
        Some(id) => id.clone(),
        None => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": "platform_user_id is required"}))
        }
    };

    match sqlx::query_as::<_, User>(
        "SELECT * FROM users WHERE platform = $1 AND platform_user_id = $2",
    )
    .bind(&platform)
    .bind(&platform_user_id)
    .fetch_optional(pool.get_ref())
    .await
    {
        Ok(Some(user)) => HttpResponse::Ok().json(UserResponse::from(user)),
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch user by platform: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/users/by_email/?email=...
#[utoipa::path(
    get,
    path = "/api/users/by_email/",
    tag = "users",
    params(("email" = String, Query, description = "User email")),
    responses(
        (status = 200, description = "User found", body = UserResponse),
        (status = 404, description = "User not found")
    )
)]
pub async fn get_user_by_email(
    pool: web::Data<PgPool>,
    query: web::Query<EmailQuery>,
) -> HttpResponse {
    let email = match &query.email {
        Some(e) if !e.is_empty() => e.clone(),
        _ => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": "email is required"}))
        }
    };

    match sqlx::query_as::<_, User>(
        "SELECT * FROM users WHERE LOWER(email) = LOWER($1)",
    )
    .bind(&email)
    .fetch_optional(pool.get_ref())
    .await
    {
        Ok(Some(user)) => HttpResponse::Ok().json(UserResponse::from(user)),
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch user by email: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/users/by_phone/?phone=...
#[utoipa::path(
    get,
    path = "/api/users/by_phone/",
    tag = "users",
    params(("phone" = String, Query, description = "User phone number")),
    responses(
        (status = 200, description = "User found", body = UserResponse),
        (status = 404, description = "User not found")
    )
)]
pub async fn get_user_by_phone(
    pool: web::Data<PgPool>,
    query: web::Query<PhoneQuery>,
) -> HttpResponse {
    let phone = match &query.phone {
        Some(p) if !p.is_empty() => {
            let p = p.clone();
            if !p.starts_with('+') {
                format!("+{}", p)
            } else {
                p
            }
        }
        _ => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": "phone is required"}))
        }
    };

    match sqlx::query_as::<_, User>(
        "SELECT * FROM users WHERE phone = $1",
    )
    .bind(&phone)
    .fetch_optional(pool.get_ref())
    .await
    {
        Ok(Some(user)) => HttpResponse::Ok().json(UserResponse::from(user)),
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch user by phone: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/users/check_exists/?platform=...&platform_user_id=...
#[utoipa::path(
    get,
    path = "/api/users/check_exists/",
    tag = "users",
    params(
        ("platform" = Option<String>, Query, description = "Platform name"),
        ("platform_user_id" = String, Query, description = "Platform user ID")
    ),
    responses(
        (status = 200, description = "Existence check result")
    )
)]
pub async fn check_user_exists(
    pool: web::Data<PgPool>,
    query: web::Query<PlatformQuery>,
) -> HttpResponse {
    let platform = query.platform.clone().unwrap_or_else(|| "telegram".to_string());
    let platform_user_id = match &query.platform_user_id {
        Some(id) => id.clone(),
        None => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": "platform_user_id is required"}))
        }
    };

    match sqlx::query_scalar::<_, bool>(
        "SELECT EXISTS(SELECT 1 FROM users WHERE platform = $1 AND platform_user_id = $2)",
    )
    .bind(&platform)
    .bind(&platform_user_id)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(exists) => HttpResponse::Ok().json(serde_json::json!({"exists": exists})),
        Err(e) => {
            tracing::error!("Failed to check user exists: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/users/{id}/balance/
#[utoipa::path(
    get,
    path = "/api/users/{id}/balance/",
    tag = "users",
    params(("id" = i32, Path, description = "User ID")),
    responses(
        (status = 200, description = "User balance", body = UserBalanceResponse),
        (status = 404, description = "User not found")
    )
)]
pub async fn get_user_balance(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let user_id = path.into_inner();
    match sqlx::query_as::<_, User>("SELECT * FROM users WHERE id = $1")
        .bind(user_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(user)) => {
            // Calculate totals from transactions
            let deposited: Decimal = sqlx::query_scalar(
                "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = $1 AND transaction_type = 'deposit'",
            )
            .bind(user_id)
            .fetch_one(pool.get_ref())
            .await
            .unwrap_or(Decimal::ZERO);

            let spent: Decimal = sqlx::query_scalar(
                "SELECT COALESCE(SUM(ABS(amount)), 0) FROM transactions WHERE user_id = $1 AND amount < 0",
            )
            .bind(user_id)
            .fetch_one(pool.get_ref())
            .await
            .unwrap_or(Decimal::ZERO);

            HttpResponse::Ok().json(UserBalanceResponse {
                balance: user.balance,
                total_deposited: deposited,
                total_spent: spent,
                available: user.balance,
            })
        }
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch user balance: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// POST /api/users/{id}/update_balance/
#[utoipa::path(
    post,
    path = "/api/users/{id}/update_balance/",
    tag = "users",
    params(("id" = i32, Path, description = "User ID")),
    request_body = UpdateBalanceRequest,
    responses(
        (status = 200, description = "Balance updated"),
        (status = 404, description = "User not found")
    )
)]
pub async fn update_user_balance(
    pool: web::Data<PgPool>,
    path: web::Path<i32>,
    body: web::Json<UpdateBalanceRequest>,
) -> HttpResponse {
    let user_id = path.into_inner();
    let amount = Decimal::try_from(body.amount).unwrap_or(Decimal::ZERO);

    match sqlx::query_as::<_, User>(
        "UPDATE users SET balance = balance + $2, updated_at = NOW() WHERE id = $1 RETURNING *",
    )
    .bind(user_id)
    .bind(amount)
    .fetch_optional(pool.get_ref())
    .await
    {
        Ok(Some(user)) => HttpResponse::Ok().json(serde_json::json!({
            "balance": user.balance,
            "message": "Balance updated successfully"
        })),
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to update balance: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/users/{id}/role/
#[utoipa::path(
    get,
    path = "/api/users/{id}/role/",
    tag = "users",
    params(("id" = i32, Path, description = "User ID")),
    responses(
        (status = 200, description = "User role"),
        (status = 404, description = "User not found")
    )
)]
pub async fn get_user_role(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let user_id = path.into_inner();
    match sqlx::query_as::<_, User>("SELECT * FROM users WHERE id = $1")
        .bind(user_id)
        .fetch_optional(pool.get_ref())
        .await
    {
        Ok(Some(user)) => {
            let role_display = match user.role.as_str() {
                "buyer" => "Buyer",
                "organizer" => "Organizer",
                "supplier" => "Supplier",
                other => other,
            };
            HttpResponse::Ok().json(serde_json::json!({
                "role": user.role,
                "role_display": role_display
            }))
        }
        Ok(None) => HttpResponse::NotFound().json(serde_json::json!({"detail": "Not found."})),
        Err(e) => {
            tracing::error!("Failed to fetch user role: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/users/search/?q=...
#[utoipa::path(
    get,
    path = "/api/users/search/",
    tag = "users",
    params(("q" = String, Query, description = "Search query (name, username, email, phone)")),
    responses(
        (status = 200, description = "Search results", body = Vec<UserResponse>),
        (status = 400, description = "Missing query parameter")
    )
)]
pub async fn search_users(
    pool: web::Data<PgPool>,
    query: web::Query<SearchQuery>,
) -> HttpResponse {
    let q = match &query.q {
        Some(q) if !q.trim().is_empty() => format!("%{}%", q.trim().to_lowercase()),
        _ => {
            return HttpResponse::BadRequest()
                .json(serde_json::json!({"error": "q (search query) is required"}))
        }
    };

    match sqlx::query_as::<_, User>(
        r#"SELECT * FROM users
           WHERE LOWER(first_name) LIKE $1
              OR LOWER(last_name) LIKE $1
              OR LOWER(username) LIKE $1
              OR LOWER(email) LIKE $1
              OR phone LIKE $1
           LIMIT 20"#,
    )
    .bind(&q)
    .fetch_all(pool.get_ref())
    .await
    {
        Ok(users) => {
            let responses: Vec<UserResponse> = users.into_iter().map(UserResponse::from).collect();
            HttpResponse::Ok().json(responses)
        }
        Err(e) => {
            tracing::error!("Failed to search users: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// GET /api/users/{id}/ws_token/
#[utoipa::path(
    get,
    path = "/api/users/{id}/ws_token/",
    tag = "users",
    params(("id" = i32, Path, description = "User ID")),
    responses(
        (status = 200, description = "WebSocket JWT token"),
        (status = 404, description = "User not found")
    )
)]
pub async fn get_ws_token(pool: web::Data<PgPool>, path: web::Path<i32>) -> HttpResponse {
    let user_id = path.into_inner();
    // Verify the user exists before issuing a token
    match sqlx::query_scalar::<_, bool>("SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)")
        .bind(user_id)
        .fetch_one(pool.get_ref())
        .await
    {
        Ok(true) => {}
        Ok(false) => {
            return HttpResponse::NotFound()
                .json(serde_json::json!({"detail": "Not found."}));
        }
        Err(e) => {
            tracing::error!("Failed to check user for ws_token: {}", e);
            return HttpResponse::InternalServerError()
                .json(serde_json::json!({"error": "Database error"}));
        }
    }

    let secret = std::env::var("JWT_SECRET").unwrap_or_else(|_| "your-secret-key".to_string());
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let claims = WsClaims {
        user_id,
        iat: now,
        exp: now + WS_TOKEN_TTL_SECS,
    };
    match encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(secret.as_bytes()),
    ) {
        Ok(token) => HttpResponse::Ok().json(serde_json::json!({
            "token": token,
            "expires_in": WS_TOKEN_TTL_SECS,
        })),
        Err(e) => {
            tracing::error!("Failed to encode ws_token JWT: {}", e);
            HttpResponse::InternalServerError()
                .json(serde_json::json!({"error": "Token generation failed"}))
        }
    }
}

// ---- Session handlers ----

/// POST /api/users/sessions/set_state/
#[utoipa::path(
    post,
    path = "/api/users/sessions/set_state/",
    tag = "users",
    request_body = SetSessionState,
    responses(
        (status = 200, description = "Session state set")
    )
)]
pub async fn set_session_state(
    pool: web::Data<PgPool>,
    body: web::Json<SetSessionState>,
) -> HttpResponse {
    let data = body.into_inner();

    let dialog_type = data.dialog_type.unwrap_or_default();
    let dialog_state = data.dialog_state.unwrap_or_default();
    let dialog_data = data
        .dialog_data
        .unwrap_or_else(|| serde_json::json!({}));

    match sqlx::query_as::<_, UserSession>(
        r#"INSERT INTO user_sessions (user_id, dialog_type, dialog_state, dialog_data)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (user_id) DO UPDATE SET
             dialog_type = EXCLUDED.dialog_type,
             dialog_state = EXCLUDED.dialog_state,
             dialog_data = EXCLUDED.dialog_data,
             updated_at = NOW()
           RETURNING *"#,
    )
    .bind(data.user_id)
    .bind(&dialog_type)
    .bind(&dialog_state)
    .bind(&dialog_data)
    .fetch_one(pool.get_ref())
    .await
    {
        Ok(session) => HttpResponse::Ok().json(session),
        Err(e) => {
            tracing::error!("Failed to set session state: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}

/// POST /api/users/sessions/clear_state/
#[utoipa::path(
    post,
    path = "/api/users/sessions/clear_state/",
    tag = "users",
    request_body = ClearSessionRequest,
    responses(
        (status = 200, description = "Session cleared")
    )
)]
pub async fn clear_session_state(
    pool: web::Data<PgPool>,
    body: web::Json<ClearSessionRequest>,
) -> HttpResponse {
    match sqlx::query("DELETE FROM user_sessions WHERE user_id = $1")
        .bind(body.user_id)
        .execute(pool.get_ref())
        .await
    {
        Ok(_) => HttpResponse::Ok().json(serde_json::json!({"message": "Session cleared"})),
        Err(e) => {
            tracing::error!("Failed to clear session: {}", e);
            HttpResponse::InternalServerError().json(serde_json::json!({"error": "Database error"}))
        }
    }
}
