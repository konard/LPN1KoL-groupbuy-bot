use chrono::{DateTime, NaiveDateTime, TimeZone, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;
use sqlx::FromRow;
use utoipa::ToSchema;

/// Deserialize a datetime field that may arrive in any of these formats:
///   - RFC 3339 / ISO 8601 with timezone: "2026-04-25T16:52:00Z"
///   - Local datetime without timezone:   "2026-04-25T16:52:00"
///   - Local datetime without seconds:    "2026-04-25T16:52"
/// All timezone-naive values are treated as UTC.
fn deserialize_flexible_datetime<'de, D>(deserializer: D) -> Result<DateTime<Utc>, D::Error>
where
    D: Deserializer<'de>,
{
    let s = String::deserialize(deserializer)?;

    // Try RFC 3339 / full ISO 8601 with offset first (e.g. "2026-04-25T16:52:00Z")
    if let Ok(dt) = DateTime::parse_from_rfc3339(&s) {
        return Ok(dt.with_timezone(&Utc));
    }

    // Try without timezone, with seconds (e.g. "2026-04-25T16:52:00")
    if let Ok(ndt) = NaiveDateTime::parse_from_str(&s, "%Y-%m-%dT%H:%M:%S") {
        return Ok(Utc.from_utc_datetime(&ndt));
    }

    // Try without timezone and without seconds (e.g. "2026-04-25T16:52")
    if let Ok(ndt) = NaiveDateTime::parse_from_str(&s, "%Y-%m-%dT%H:%M") {
        return Ok(Utc.from_utc_datetime(&ndt));
    }

    Err(serde::de::Error::custom(format!(
        "invalid datetime format: '{}'. Expected ISO 8601, e.g. '2026-04-25T16:52' or '2026-04-25T16:52:00Z'",
        s
    )))
}

/// Same as `deserialize_flexible_datetime` but for `Option<DateTime<Utc>>`.
fn deserialize_flexible_datetime_opt<'de, D>(
    deserializer: D,
) -> Result<Option<DateTime<Utc>>, D::Error>
where
    D: Deserializer<'de>,
{
    let opt = Option::<String>::deserialize(deserializer)?;
    match opt {
        None => Ok(None),
        Some(s) => {
            if let Ok(dt) = DateTime::parse_from_rfc3339(&s) {
                return Ok(Some(dt.with_timezone(&Utc)));
            }
            if let Ok(ndt) = NaiveDateTime::parse_from_str(&s, "%Y-%m-%dT%H:%M:%S") {
                return Ok(Some(Utc.from_utc_datetime(&ndt)));
            }
            if let Ok(ndt) = NaiveDateTime::parse_from_str(&s, "%Y-%m-%dT%H:%M") {
                return Ok(Some(Utc.from_utc_datetime(&ndt)));
            }
            Err(serde::de::Error::custom(format!(
                "invalid datetime format: '{}'. Expected ISO 8601, e.g. '2026-04-25T16:52' or '2026-04-25T16:52:00Z'",
                s
            )))
        }
    }
}

/// Deserialize an optional integer that may arrive as a JSON number or a numeric string.
/// Accepts: null, 42, "42", "". Returns None for null or empty string.
fn deserialize_opt_int_or_str<'de, D>(deserializer: D) -> Result<Option<i32>, D::Error>
where
    D: Deserializer<'de>,
{
    let v = Value::deserialize(deserializer)?;
    match v {
        Value::Null => Ok(None),
        Value::Number(n) => n
            .as_i64()
            .map(|n| Some(n as i32))
            .ok_or_else(|| serde::de::Error::custom("expected integer")),
        Value::String(s) if s.is_empty() => Ok(None),
        Value::String(s) => s
            .parse::<i32>()
            .map(Some)
            .map_err(|_| serde::de::Error::custom(format!("cannot parse '{}' as integer", s))),
        other => Err(serde::de::Error::custom(format!(
            "expected integer or string, got {:?}",
            other
        ))),
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow, ToSchema)]
pub struct Category {
    pub id: i32,
    pub name: String,
    pub description: String,
    pub parent_id: Option<i32>,
    pub icon: String,
    pub is_active: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow, ToSchema)]
pub struct Procurement {
    pub id: i32,
    pub title: String,
    pub description: String,
    pub category_id: Option<i32>,
    pub organizer_id: i32,
    pub supplier_id: Option<i32>,
    pub city: String,
    pub delivery_address: String,
    pub target_amount: Decimal,
    pub current_amount: Decimal,
    pub stop_at_amount: Option<Decimal>,
    pub unit: String,
    pub price_per_unit: Option<Decimal>,
    pub status: String,
    pub commission_percent: Decimal,
    pub min_quantity: Option<Decimal>,
    pub deadline: DateTime<Utc>,
    pub payment_deadline: Option<DateTime<Utc>>,
    pub image_url: String,
    pub is_featured: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Serialize, ToSchema)]
pub struct ProcurementResponse {
    pub id: i32,
    pub title: String,
    pub description: String,
    pub category_id: Option<i32>,
    pub organizer_id: i32,
    pub supplier_id: Option<i32>,
    pub city: String,
    pub delivery_address: String,
    pub target_amount: Decimal,
    pub current_amount: Decimal,
    pub stop_at_amount: Option<Decimal>,
    pub unit: String,
    pub price_per_unit: Option<Decimal>,
    pub status: String,
    pub status_display: String,
    pub commission_percent: Decimal,
    pub min_quantity: Option<Decimal>,
    pub deadline: DateTime<Utc>,
    pub payment_deadline: Option<DateTime<Utc>>,
    pub image_url: String,
    pub is_featured: bool,
    pub progress: i32,
    pub participant_count: i64,
    pub days_left: i64,
    pub can_join: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

impl Procurement {
    pub fn to_response(self, participant_count: i64) -> ProcurementResponse {
        let status_display = match self.status.as_str() {
            "draft" => "Draft",
            "active" => "Active",
            "stopped" => "Stopped",
            "payment" => "Payment in Progress",
            "completed" => "Completed",
            "cancelled" => "Cancelled",
            other => other,
        }
        .to_string();

        let progress = if self.target_amount.is_zero() {
            0
        } else {
            let pct = (self.current_amount / self.target_amount * Decimal::from(100))
                .to_string()
                .parse::<i32>()
                .unwrap_or(0);
            pct.min(100)
        };

        let days_left = (self.deadline - Utc::now()).num_days().max(0);

        let can_join = self.status == "active"
            && self.deadline > Utc::now()
            && self
                .stop_at_amount
                .map_or(true, |stop| self.current_amount < stop);

        ProcurementResponse {
            id: self.id,
            title: self.title,
            description: self.description,
            category_id: self.category_id,
            organizer_id: self.organizer_id,
            supplier_id: self.supplier_id,
            city: self.city,
            delivery_address: self.delivery_address,
            target_amount: self.target_amount,
            current_amount: self.current_amount,
            stop_at_amount: self.stop_at_amount,
            unit: self.unit,
            price_per_unit: self.price_per_unit,
            status: self.status,
            status_display,
            commission_percent: self.commission_percent,
            min_quantity: self.min_quantity,
            deadline: self.deadline,
            payment_deadline: self.payment_deadline,
            image_url: self.image_url,
            is_featured: self.is_featured,
            progress,
            participant_count,
            days_left,
            can_join,
            created_at: self.created_at,
            updated_at: self.updated_at,
        }
    }
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct CreateProcurement {
    pub title: String,
    pub description: String,
    /// Accepts both `category_id` (integer) and `category` (integer or numeric string).
    #[serde(
        alias = "category",
        deserialize_with = "deserialize_opt_int_or_str",
        default
    )]
    pub category_id: Option<i32>,
    /// Accepts both `organizer_id` and `organizer`.
    #[serde(alias = "organizer")]
    pub organizer_id: i32,
    pub city: String,
    pub delivery_address: Option<String>,
    pub target_amount: Decimal,
    pub stop_at_amount: Option<Decimal>,
    pub unit: Option<String>,
    pub price_per_unit: Option<Decimal>,
    pub status: Option<String>,
    pub commission_percent: Option<Decimal>,
    pub min_quantity: Option<Decimal>,
    #[serde(deserialize_with = "deserialize_flexible_datetime")]
    pub deadline: DateTime<Utc>,
    #[serde(deserialize_with = "deserialize_flexible_datetime_opt", default)]
    pub payment_deadline: Option<DateTime<Utc>>,
    pub image_url: Option<String>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct ProcurementQuery {
    pub status: Option<String>,
    pub city: Option<String>,
    pub category_id: Option<i32>,
    pub organizer_id: Option<i32>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow, ToSchema)]
pub struct Participant {
    pub id: i32,
    pub procurement_id: i32,
    pub user_id: i32,
    pub quantity: Decimal,
    pub amount: Decimal,
    pub status: String,
    pub notes: String,
    pub is_active: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize, ToSchema)]
pub struct JoinProcurement {
    pub user_id: Option<i32>,
    pub amount: Decimal,
    pub quantity: Option<Decimal>,
    pub notes: Option<String>,
}
