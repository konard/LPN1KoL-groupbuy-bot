use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use utoipa::ToSchema;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, FromRow, ToSchema)]
pub struct Message {
    pub id: i32,
    pub procurement_id: i32,
    pub user_id: Option<Uuid>,
    pub message_type: String,
    pub text: String,
    pub attachment_url: String,
    pub is_edited: bool,
    pub is_deleted: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct CreateMessage {
    pub procurement: i32,
    pub user: Option<Uuid>,
    pub text: String,
    pub message_type: Option<String>,
    pub attachment_url: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct MessageQuery {
    pub procurement: Option<i32>,
    pub user: Option<Uuid>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow, ToSchema)]
pub struct Notification {
    pub id: i32,
    pub user_id: Uuid,
    pub notification_type: String,
    pub title: String,
    pub message: String,
    pub procurement_id: Option<i32>,
    pub is_read: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct NotificationQuery {
    pub user_id: Option<Uuid>,
}
