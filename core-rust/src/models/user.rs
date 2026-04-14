use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use utoipa::ToSchema;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct User {
    pub id: Uuid,
    pub platform: String,
    pub platform_user_id: String,
    pub username: String,
    pub first_name: String,
    pub last_name: String,
    pub phone: String,
    pub email: String,
    pub role: String,
    pub balance: Decimal,
    pub language_code: String,
    pub is_active: bool,
    pub is_verified: bool,
    pub is_banned: bool,
    pub selfie_file_id: String,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct CreateUser {
    pub platform: Option<String>,
    pub platform_user_id: String,
    pub username: Option<String>,
    pub first_name: Option<String>,
    pub last_name: Option<String>,
    pub phone: Option<String>,
    pub email: Option<String>,
    pub role: Option<String>,
    pub language_code: Option<String>,
    pub selfie_file_id: Option<String>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct UpdateUser {
    pub first_name: Option<String>,
    pub last_name: Option<String>,
    pub phone: Option<String>,
    pub email: Option<String>,
    pub role: Option<String>,
}

#[derive(Debug, Serialize, ToSchema)]
pub struct UserResponse {
    pub id: Uuid,
    pub platform: String,
    pub platform_user_id: String,
    pub username: String,
    pub first_name: String,
    pub last_name: String,
    pub full_name: String,
    pub phone: String,
    pub email: String,
    pub role: String,
    pub role_display: String,
    pub balance: Decimal,
    pub language_code: String,
    pub is_active: bool,
    pub is_verified: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

impl From<User> for UserResponse {
    fn from(u: User) -> Self {
        let full_name = format!("{} {}", u.first_name, u.last_name).trim().to_string();
        let role_display = match u.role.as_str() {
            "buyer" => "Buyer".to_string(),
            "organizer" => "Organizer".to_string(),
            "supplier" => "Supplier".to_string(),
            other => other.to_string(),
        };
        UserResponse {
            id: u.id,
            platform: u.platform,
            platform_user_id: u.platform_user_id,
            username: u.username,
            first_name: u.first_name,
            last_name: u.last_name,
            full_name,
            phone: u.phone,
            email: u.email,
            role: u.role,
            role_display,
            balance: u.balance,
            language_code: u.language_code,
            is_active: u.is_active,
            is_verified: u.is_verified,
            created_at: u.created_at,
            updated_at: u.updated_at,
        }
    }
}

#[derive(Debug, Serialize, ToSchema)]
pub struct UserBalanceResponse {
    pub balance: Decimal,
    pub total_deposited: Decimal,
    pub total_spent: Decimal,
    pub available: Decimal,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct UpdateBalanceRequest {
    pub amount: f64,
}

#[derive(Debug, Deserialize)]
pub struct PlatformQuery {
    pub platform: Option<String>,
    pub platform_user_id: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct EmailQuery {
    pub email: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct PhoneQuery {
    pub phone: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct SearchQuery {
    pub q: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct UserSession {
    pub id: i32,
    pub user_id: Uuid,
    pub dialog_type: String,
    pub dialog_state: String,
    pub dialog_data: serde_json::Value,
    pub expires_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct SetSessionState {
    pub user_id: Uuid,
    pub dialog_type: Option<String>,
    pub dialog_state: Option<String>,
    pub dialog_data: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct ClearSessionRequest {
    pub user_id: Uuid,
}
