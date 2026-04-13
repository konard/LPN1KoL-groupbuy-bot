mod db;
mod handlers;
mod models;

use actix_cors::Cors;
use actix_web::{web, App, HttpResponse, HttpServer};
use std::sync::Arc;
use tracing_actix_web::TracingLogger;
use utoipa::OpenApi;
use utoipa_swagger_ui::SwaggerUi;

use handlers::websocket::WsState;

#[derive(OpenApi)]
#[openapi(
    info(
        title = "GroupBuy Bot API",
        version = "1.0.0",
        description = "API for GroupBuy Bot — a multi-platform group purchasing bot"
    ),
    paths(
        handlers::users::list_users,
        handlers::users::create_user,
        handlers::users::get_user,
        handlers::users::update_user,
        handlers::users::delete_user,
        handlers::users::get_user_by_platform,
        handlers::users::get_user_by_email,
        handlers::users::get_user_by_phone,
        handlers::users::check_user_exists,
        handlers::users::get_user_balance,
        handlers::users::update_user_balance,
        handlers::users::get_user_role,
        handlers::users::get_ws_token,
        handlers::users::search_users,
        handlers::users::set_session_state,
        handlers::users::clear_session_state,
        handlers::procurements::list_procurements,
        handlers::procurements::create_procurement,
        handlers::procurements::get_procurement,
        handlers::procurements::get_user_procurements,
        handlers::procurements::join_procurement,
        handlers::procurements::leave_procurement,
        handlers::procurements::list_categories,
        handlers::payments::create_payment,
        handlers::payments::get_payment_status,
        handlers::chat::list_messages,
        handlers::chat::create_message,
        handlers::chat::list_notifications,
    ),
    components(
        schemas(
            models::user::UserResponse,
            models::user::CreateUser,
            models::user::UpdateUser,
            models::user::UserBalanceResponse,
            models::user::UpdateBalanceRequest,
            models::user::SetSessionState,
            models::user::ClearSessionRequest,
            models::procurement::Category,
            models::procurement::ProcurementResponse,
            models::procurement::CreateProcurement,
            models::procurement::Participant,
            models::procurement::JoinProcurement,
            models::payment::Payment,
            models::payment::CreatePayment,
            models::payment::PaymentStatusResponse,
            models::chat::Message,
            models::chat::CreateMessage,
            models::chat::Notification,
        )
    ),
    tags(
        (name = "users", description = "User management endpoints"),
        (name = "procurements", description = "Procurement endpoints"),
        (name = "payments", description = "Payment endpoints"),
        (name = "chat", description = "Chat and notification endpoints"),
    )
)]
struct ApiDoc;

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // Load .env file
    dotenvy::dotenv().ok();

    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info,groupbuy_api=debug".into()),
        )
        .init();

    // Database connection
    let database_url = std::env::var("DATABASE_URL").unwrap_or_else(|_| {
        let host = std::env::var("DB_HOST").unwrap_or_else(|_| "localhost".into());
        let port = std::env::var("DB_PORT").unwrap_or_else(|_| "5432".into());
        let name = std::env::var("DB_NAME").unwrap_or_else(|_| "groupbuy".into());
        let user = std::env::var("DB_USER").unwrap_or_else(|_| "postgres".into());
        let pass = std::env::var("DB_PASSWORD").unwrap_or_else(|_| "postgres".into());
        format!("postgres://{}:{}@{}:{}/{}", user, pass, host, port, name)
    });

    tracing::info!("Connecting to database...");
    let pool = db::create_pool(&database_url)
        .await
        .expect("Failed to create database pool");

    // Run migrations
    db::run_migrations(&pool)
        .await
        .expect("Failed to run migrations");

    // WebSocket state
    let ws_state = Arc::new(WsState::new());

    let bind_addr = std::env::var("BIND_ADDR").unwrap_or_else(|_| "0.0.0.0".into());
    let bind_port: u16 = std::env::var("PORT")
        .unwrap_or_else(|_| "8000".into())
        .parse()
        .unwrap_or(8000);

    tracing::info!("Starting server on {}:{}", bind_addr, bind_port);

    // Build OpenAPI spec once, outside the HttpServer closure
    let openapi = ApiDoc::openapi();

    HttpServer::new(move || {
        let cors = Cors::default()
            .allow_any_origin()
            .allow_any_method()
            .allow_any_header()
            .max_age(3600);

        // Return a structured JSON error when JSON deserialization fails (e.g. truncated
        // or malformed request body) instead of the default plain-text 400 response.
        let json_cfg = web::JsonConfig::default()
            .error_handler(|err, _req| {
                let message = err.to_string();
                tracing::warn!("JSON deserialization error: {}", message);
                let response = HttpResponse::BadRequest()
                    .json(serde_json::json!({"error": message}));
                actix_web::error::InternalError::from_response(err, response).into()
            });

        App::new()
            .wrap(TracingLogger::default())
            .wrap(cors)
            .app_data(json_cfg)
            .app_data(web::Data::new(pool.clone()))
            .app_data(web::Data::new(ws_state.clone()))
            // Swagger UI — available at /api/docs/
            .service(
                SwaggerUi::new("/api/docs/{_:.*}")
                    .url("/api/schema/openapi.json", openapi.clone()),
            )
            // User endpoints
            .route("/api/users/", web::get().to(handlers::users::list_users))
            .route("/api/users/", web::post().to(handlers::users::create_user))
            .route("/api/users/by_platform/", web::get().to(handlers::users::get_user_by_platform))
            .route("/api/users/by_email/", web::get().to(handlers::users::get_user_by_email))
            .route("/api/users/by_phone/", web::get().to(handlers::users::get_user_by_phone))
            .route("/api/users/check_exists/", web::get().to(handlers::users::check_user_exists))
            .route("/api/users/search/", web::get().to(handlers::users::search_users))
            .route("/api/users/sessions/set_state/", web::post().to(handlers::users::set_session_state))
            .route("/api/users/sessions/clear_state/", web::post().to(handlers::users::clear_session_state))
            .route("/api/users/{id}/", web::get().to(handlers::users::get_user))
            .route("/api/users/{id}/", web::put().to(handlers::users::update_user))
            .route("/api/users/{id}/", web::patch().to(handlers::users::update_user))
            .route("/api/users/{id}/", web::delete().to(handlers::users::delete_user))
            .route("/api/users/{id}/balance/", web::get().to(handlers::users::get_user_balance))
            .route("/api/users/{id}/update_balance/", web::post().to(handlers::users::update_user_balance))
            .route("/api/users/{id}/role/", web::get().to(handlers::users::get_user_role))
            .route("/api/users/{id}/ws_token/", web::get().to(handlers::users::get_ws_token))
            // Procurement endpoints
            .route("/api/procurements/", web::get().to(handlers::procurements::list_procurements))
            .route("/api/procurements/", web::post().to(handlers::procurements::create_procurement))
            .route("/api/procurements/categories/", web::get().to(handlers::procurements::list_categories))
            .route("/api/procurements/user/{user_id}/", web::get().to(handlers::procurements::get_user_procurements))
            .route("/api/procurements/{id}/", web::get().to(handlers::procurements::get_procurement))
            .route("/api/procurements/{id}/join/", web::post().to(handlers::procurements::join_procurement))
            .route("/api/procurements/{id}/leave/", web::post().to(handlers::procurements::leave_procurement))
            // Chat endpoints
            .route("/api/chat/messages/", web::get().to(handlers::chat::list_messages))
            .route("/api/chat/messages/", web::post().to(handlers::chat::create_message))
            .route("/api/chat/messages/mark_read/", web::post().to(handlers::chat::mark_messages_read))
            .route("/api/chat/notifications/", web::get().to(handlers::chat::list_notifications))
            .route("/api/chat/notifications/{id}/mark_read/", web::post().to(handlers::chat::mark_notification_read))
            // Payment endpoints
            .route("/api/payments/", web::post().to(handlers::payments::create_payment))
            .route("/api/payments/{id}/status/", web::get().to(handlers::payments::get_payment_status))
            // WebSocket endpoint
            .route("/ws/chat/", web::get().to(handlers::websocket::ws_handler))
            // Health check endpoint
            .route("/health/", web::get().to(|| async { actix_web::HttpResponse::Ok().body("OK") }))
            .route("/health", web::get().to(|| async { actix_web::HttpResponse::Ok().body("OK") }))
    })
    .bind((bind_addr, bind_port))?
    .run()
    .await
}
