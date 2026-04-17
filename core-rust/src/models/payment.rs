use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use utoipa::ToSchema;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, FromRow, ToSchema)]
pub struct Payment {
    pub id: i32,
    pub user_id: Uuid,
    pub payment_type: String,
    pub amount: Decimal,
    pub status: String,
    pub external_id: Option<String>,
    pub provider: String,
    pub confirmation_url: String,
    pub procurement_id: Option<i32>,
    pub description: String,
    pub metadata: serde_json::Value,
    pub paid_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct CreatePayment {
    pub user_id: Uuid,
    pub payment_type: String,
    pub amount: Decimal,
    pub procurement_id: Option<i32>,
    pub description: Option<String>,
}

#[derive(Debug, Serialize, ToSchema)]
pub struct PaymentStatusResponse {
    pub id: i32,
    pub status: String,
    pub status_display: String,
    pub amount: Decimal,
    pub confirmation_url: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow, ToSchema)]
pub struct Transaction {
    pub id: i32,
    pub user_id: Uuid,
    pub transaction_type: String,
    pub amount: Decimal,
    pub balance_after: Decimal,
    pub payment_id: Option<i32>,
    pub procurement_id: Option<i32>,
    pub description: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct PaymentQuery {
    pub user_id: Option<Uuid>,
    pub payment_type: Option<String>,
    pub status: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct TransactionQuery {
    pub user_id: Option<Uuid>,
    pub transaction_type: Option<String>,
}

#[derive(Debug, Serialize, ToSchema)]
pub struct TransactionSummary {
    pub current_balance: Decimal,
    pub total_deposited: Decimal,
    pub total_withdrawn: Decimal,
    pub total_refunded: Decimal,
    pub transaction_count: i64,
}
