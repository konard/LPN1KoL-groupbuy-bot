use wasm_bindgen::prelude::*;
use serde::{Deserialize, Serialize};

// ──────────────────────────────────────────────
// Validation functions
// ──────────────────────────────────────────────

/// Validate phone number format (Russian phone number)
#[wasm_bindgen]
pub fn validate_phone(phone: &str) -> bool {
    let cleaned: String = phone.chars().filter(|c| c.is_ascii_digit() || *c == '+').collect();
    if cleaned.is_empty() {
        return true; // phone is optional
    }
    let re_pattern = cleaned.starts_with('+') && cleaned.len() >= 11 && cleaned.len() <= 16;
    let digits_only = cleaned.trim_start_matches('+');
    re_pattern && digits_only.chars().all(|c| c.is_ascii_digit())
}

/// Validate email format
#[wasm_bindgen]
pub fn validate_email(email: &str) -> bool {
    if email.is_empty() {
        return true; // email is optional
    }
    let parts: Vec<&str> = email.split('@').collect();
    if parts.len() != 2 {
        return false;
    }
    let local = parts[0];
    let domain = parts[1];
    !local.is_empty() && domain.contains('.') && domain.len() > 2
}

/// Validate procurement form data
/// Returns JSON string with validation errors (empty object if valid)
#[wasm_bindgen]
pub fn validate_procurement_form(title: &str, description: &str, city: &str, target_amount: f64, deadline_ms: f64) -> String {
    let mut errors: Vec<(&str, &str)> = Vec::new();

    if title.trim().is_empty() {
        errors.push(("title", "Название обязательно"));
    } else if title.len() > 200 {
        errors.push(("title", "Название не должно превышать 200 символов"));
    }

    if description.trim().is_empty() {
        errors.push(("description", "Описание обязательно"));
    }

    if city.trim().is_empty() {
        errors.push(("city", "Город обязателен"));
    }

    if target_amount <= 0.0 {
        errors.push(("target_amount", "Целевая сумма должна быть положительной"));
    }

    let now_ms = js_sys::Date::now();
    if deadline_ms <= now_ms {
        errors.push(("deadline", "Дедлайн должен быть в будущем"));
    }

    if errors.is_empty() {
        "{}".to_string()
    } else {
        let mut result = String::from("{");
        for (i, (key, msg)) in errors.iter().enumerate() {
            if i > 0 {
                result.push(',');
            }
            result.push_str(&format!("\"{}\":\"{}\"", key, msg));
        }
        result.push('}');
        result
    }
}

// ──────────────────────────────────────────────
// Formatting functions
// ──────────────────────────────────────────────

/// Calculate procurement progress percentage
#[wasm_bindgen]
pub fn calculate_progress(current_amount: f64, target_amount: f64) -> i32 {
    if target_amount <= 0.0 {
        return 0;
    }
    let progress = (current_amount / target_amount * 100.0) as i32;
    progress.min(100).max(0)
}

/// Calculate days remaining until deadline
#[wasm_bindgen]
pub fn days_until(deadline_ms: f64) -> i32 {
    let now_ms = js_sys::Date::now();
    let diff_ms = deadline_ms - now_ms;
    let days = (diff_ms / 86_400_000.0) as i32;
    days.max(0)
}

/// Format currency amount (Russian rubles)
#[wasm_bindgen]
pub fn format_currency(amount: f64) -> String {
    let integer = amount.trunc() as i64;
    let fraction = ((amount.fract() * 100.0).round() as i64).abs();

    // Format with thousands separator
    let int_str = integer.to_string();
    let mut formatted = String::new();
    for (i, ch) in int_str.chars().rev().enumerate() {
        if i > 0 && i % 3 == 0 && ch != '-' {
            formatted.push(' ');
        }
        formatted.push(ch);
    }
    let formatted: String = formatted.chars().rev().collect();

    if fraction > 0 {
        format!("{},{:02} \u{20bd}", formatted, fraction)
    } else {
        format!("{} \u{20bd}", formatted)
    }
}

/// Format relative time in Russian
#[wasm_bindgen]
pub fn format_relative_time(timestamp_ms: f64) -> String {
    let now_ms = js_sys::Date::now();
    let diff_sec = ((now_ms - timestamp_ms) / 1000.0) as i64;

    if diff_sec < 60 {
        return "только что".to_string();
    }
    if diff_sec < 3600 {
        let mins = diff_sec / 60;
        return format!("{} мин. назад", mins);
    }
    if diff_sec < 86400 {
        let hours = diff_sec / 3600;
        return format!("{} ч. назад", hours);
    }
    let days = diff_sec / 86400;
    if days == 1 {
        return "вчера".to_string();
    }
    format!("{} дн. назад", days)
}

/// Generate unique platform user ID for websocket users
#[wasm_bindgen]
pub fn generate_platform_user_id() -> String {
    let timestamp = js_sys::Date::now() as u64;
    let random = (js_sys::Math::random() * 1_000_000_000.0) as u64;
    format!("web_{}_{}", timestamp, random)
}

/// Generate avatar background color based on name (hash-based)
#[wasm_bindgen]
pub fn get_avatar_color(name: &str) -> String {
    let colors = [
        "#e17076", "#faa774", "#a695e7", "#7bc862",
        "#6ec9cb", "#65aadd", "#ee7aae", "#f5a623",
    ];
    let mut hash: i32 = 0;
    for ch in name.chars() {
        hash = (ch as i32).wrapping_add(hash.wrapping_shl(5).wrapping_sub(hash));
    }
    colors[(hash.unsigned_abs() as usize) % colors.len()].to_string()
}

/// Get initials from first name and last name
#[wasm_bindgen]
pub fn get_initials(first_name: &str, last_name: &str) -> String {
    let first = first_name.chars().next().map(|c| c.to_uppercase().to_string()).unwrap_or_default();
    let last = last_name.chars().next().map(|c| c.to_uppercase().to_string()).unwrap_or_default();
    let result = format!("{}{}", first, last);
    if result.is_empty() {
        "?".to_string()
    } else {
        result
    }
}

/// Escape HTML to prevent XSS
#[wasm_bindgen]
pub fn escape_html(text: &str) -> String {
    let mut result = String::with_capacity(text.len());
    for ch in text.chars() {
        match ch {
            '&' => result.push_str("&amp;"),
            '<' => result.push_str("&lt;"),
            '>' => result.push_str("&gt;"),
            '"' => result.push_str("&quot;"),
            '\'' => result.push_str("&#x27;"),
            _ => result.push(ch),
        }
    }
    result
}

/// Format message text: escape HTML, convert URLs to links, convert newlines to <br>
#[wasm_bindgen]
pub fn format_message_text(text: &str) -> String {
    if text.is_empty() {
        return String::new();
    }

    let escaped = escape_html(text);

    // Convert URLs to clickable links
    let mut result = String::with_capacity(escaped.len());
    let mut remaining = escaped.as_str();

    while !remaining.is_empty() {
        if let Some(http_pos) = remaining.find("http") {
            let before = &remaining[..http_pos];
            result.push_str(before);

            let after = &remaining[http_pos..];
            // Check if it's https:// or http://
            let is_url = after.starts_with("https://") || after.starts_with("http://");

            if is_url {
                // Find end of URL (whitespace or end of string)
                let url_end = after.find(|c: char| c.is_whitespace() || c == '<')
                    .unwrap_or(after.len());
                let url = &after[..url_end];
                result.push_str(&format!("<a href=\"{}\" target=\"_blank\" rel=\"noopener\">{}</a>", url, url));
                remaining = &after[url_end..];
            } else {
                result.push_str(&after[..4]);
                remaining = &after[4..];
            }
        } else {
            result.push_str(remaining);
            break;
        }
    }

    // Convert newlines to <br>
    result.replace('\n', "<br>")
}

// ──────────────────────────────────────────────
// High-performance batch processing functions
// ──────────────────────────────────────────────

/// Procurement data for batch operations (internal)
#[derive(Serialize, Deserialize, Clone)]
struct Procurement {
    id: i64,
    title: String,
    description: Option<String>,
    city: Option<String>,
    status: Option<String>,
    current_amount: Option<f64>,
    target_amount: Option<f64>,
    deadline: Option<String>,
    participant_count: Option<i32>,
    category: Option<String>,
    organizer_name: Option<String>,
    created_at: Option<String>,
    #[serde(default)]
    progress: Option<f64>,
}

/// Batch-process procurements: compute progress, days left, and format currency in one pass
/// Input: JSON array of procurements
/// Output: JSON array with computed fields added
#[wasm_bindgen]
pub fn batch_process_procurements(json_input: &str) -> String {
    let procurements: Vec<Procurement> = match serde_json::from_str(json_input) {
        Ok(p) => p,
        Err(_) => return "[]".to_string(),
    };

    let now_ms = js_sys::Date::now();
    let results: Vec<serde_json::Value> = procurements.iter().map(|p| {
        let current = p.current_amount.unwrap_or(0.0);
        let target = p.target_amount.unwrap_or(0.0);
        let progress = if target > 0.0 {
            ((current / target * 100.0) as i32).min(100).max(0)
        } else {
            0
        };

        let days_left = p.deadline.as_ref().map(|d| {
            // Parse ISO date string to ms
            let date = js_sys::Date::new(&JsValue::from_str(d));
            let deadline_ms = date.get_time();
            let diff_ms = deadline_ms - now_ms;
            ((diff_ms / 86_400_000.0) as i32).max(0)
        });

        let formatted_current = format_currency_value(current);
        let formatted_target = format_currency_value(target);

        let mut obj = serde_json::json!({
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "city": p.city,
            "status": p.status,
            "current_amount": current,
            "target_amount": target,
            "participant_count": p.participant_count,
            "category": p.category,
            "organizer_name": p.organizer_name,
            "created_at": p.created_at,
            "deadline": p.deadline,
            "progress": progress,
            "formatted_current": formatted_current,
            "formatted_target": formatted_target,
        });

        if let Some(days) = days_left {
            obj["days_left"] = serde_json::json!(days);
        }

        obj
    }).collect();

    serde_json::to_string(&results).unwrap_or_else(|_| "[]".to_string())
}

/// Internal helper: format currency without the symbol for reuse
fn format_currency_value(amount: f64) -> String {
    let integer = amount.trunc() as i64;
    let fraction = ((amount.fract() * 100.0).round() as i64).abs();

    let int_str = integer.to_string();
    let mut formatted = String::new();
    for (i, ch) in int_str.chars().rev().enumerate() {
        if i > 0 && i % 3 == 0 && ch != '-' {
            formatted.push(' ');
        }
        formatted.push(ch);
    }
    let formatted: String = formatted.chars().rev().collect();

    if fraction > 0 {
        format!("{},{:02} \u{20bd}", formatted, fraction)
    } else {
        format!("{} \u{20bd}", formatted)
    }
}

/// Fuzzy search procurements by query string
/// Returns JSON array of matching procurement IDs with relevance scores, sorted by relevance
#[wasm_bindgen]
pub fn search_procurements(json_input: &str, query: &str) -> String {
    if query.trim().is_empty() {
        return "[]".to_string();
    }

    let procurements: Vec<Procurement> = match serde_json::from_str(json_input) {
        Ok(p) => p,
        Err(_) => return "[]".to_string(),
    };

    let query_lower = query.to_lowercase();
    let query_words: Vec<&str> = query_lower.split_whitespace().collect();

    let mut results: Vec<(i64, f64)> = procurements.iter().filter_map(|p| {
        let mut score: f64 = 0.0;
        let title_lower = p.title.to_lowercase();
        let desc_lower = p.description.as_deref().unwrap_or("").to_lowercase();
        let city_lower = p.city.as_deref().unwrap_or("").to_lowercase();
        let org_lower = p.organizer_name.as_deref().unwrap_or("").to_lowercase();

        for word in &query_words {
            // Title matches (highest weight)
            if title_lower.contains(word) {
                score += 10.0;
                if title_lower.starts_with(word) {
                    score += 5.0; // prefix bonus
                }
            }
            // City match
            if city_lower.contains(word) {
                score += 5.0;
            }
            // Organizer match
            if org_lower.contains(word) {
                score += 3.0;
            }
            // Description match (lower weight)
            if desc_lower.contains(word) {
                score += 2.0;
            }
        }

        if score > 0.0 {
            Some((p.id, score))
        } else {
            None
        }
    }).collect();

    // Sort by relevance score descending
    results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

    let output: Vec<serde_json::Value> = results.iter().map(|(id, score)| {
        serde_json::json!({"id": id, "score": score})
    }).collect();

    serde_json::to_string(&output).unwrap_or_else(|_| "[]".to_string())
}

/// Sort procurements by a specified field
/// sort_by: "title", "amount", "progress", "deadline", "participants", "created"
/// order: "asc" or "desc"
/// Returns JSON array of sorted procurement IDs
#[wasm_bindgen]
pub fn sort_procurements(json_input: &str, sort_by: &str, order: &str) -> String {
    let mut procurements: Vec<Procurement> = match serde_json::from_str(json_input) {
        Ok(p) => p,
        Err(_) => return "[]".to_string(),
    };

    let ascending = order != "desc";

    procurements.sort_by(|a, b| {
        let cmp = match sort_by {
            "title" => a.title.to_lowercase().cmp(&b.title.to_lowercase()),
            "amount" => {
                let a_val = a.current_amount.unwrap_or(0.0);
                let b_val = b.current_amount.unwrap_or(0.0);
                a_val.partial_cmp(&b_val).unwrap_or(std::cmp::Ordering::Equal)
            }
            "progress" => {
                let a_target = a.target_amount.unwrap_or(1.0);
                let b_target = b.target_amount.unwrap_or(1.0);
                let a_prog = if a_target > 0.0 { a.current_amount.unwrap_or(0.0) / a_target } else { 0.0 };
                let b_prog = if b_target > 0.0 { b.current_amount.unwrap_or(0.0) / b_target } else { 0.0 };
                a_prog.partial_cmp(&b_prog).unwrap_or(std::cmp::Ordering::Equal)
            }
            "deadline" => {
                let a_val = a.deadline.as_deref().unwrap_or("");
                let b_val = b.deadline.as_deref().unwrap_or("");
                a_val.cmp(b_val)
            }
            "participants" => {
                let a_val = a.participant_count.unwrap_or(0);
                let b_val = b.participant_count.unwrap_or(0);
                a_val.cmp(&b_val)
            }
            "created" => {
                let a_val = a.created_at.as_deref().unwrap_or("");
                let b_val = b.created_at.as_deref().unwrap_or("");
                a_val.cmp(b_val)
            }
            _ => std::cmp::Ordering::Equal,
        };
        if ascending { cmp } else { cmp.reverse() }
    });

    let ids: Vec<i64> = procurements.iter().map(|p| p.id).collect();
    serde_json::to_string(&ids).unwrap_or_else(|_| "[]".to_string())
}

/// Aggregate procurement statistics from a JSON array
/// Returns JSON object with: total_count, active_count, total_amount, total_target,
/// overall_progress, avg_participants, cities (unique), by_status counts
#[wasm_bindgen]
pub fn aggregate_procurement_stats(json_input: &str) -> String {
    let procurements: Vec<Procurement> = match serde_json::from_str(json_input) {
        Ok(p) => p,
        Err(_) => return "{}".to_string(),
    };

    let total_count = procurements.len();
    let mut active_count = 0;
    let mut total_amount = 0.0_f64;
    let mut total_target = 0.0_f64;
    let mut total_participants = 0_i64;
    let mut cities: Vec<String> = Vec::new();
    let mut status_counts: std::collections::HashMap<String, i32> = std::collections::HashMap::new();

    for p in &procurements {
        let status = p.status.as_deref().unwrap_or("unknown");
        if status == "active" {
            active_count += 1;
        }
        *status_counts.entry(status.to_string()).or_insert(0) += 1;

        total_amount += p.current_amount.unwrap_or(0.0);
        total_target += p.target_amount.unwrap_or(0.0);
        total_participants += p.participant_count.unwrap_or(0) as i64;

        if let Some(city) = &p.city {
            if !city.is_empty() && !cities.contains(city) {
                cities.push(city.clone());
            }
        }
    }

    let overall_progress = if total_target > 0.0 {
        ((total_amount / total_target * 100.0) as i32).min(100).max(0)
    } else {
        0
    };

    let avg_participants = if total_count > 0 {
        total_participants as f64 / total_count as f64
    } else {
        0.0
    };

    let result = serde_json::json!({
        "total_count": total_count,
        "active_count": active_count,
        "total_amount": total_amount,
        "total_target": total_target,
        "overall_progress": overall_progress,
        "avg_participants": (avg_participants * 10.0).round() / 10.0,
        "cities": cities,
        "by_status": status_counts,
        "formatted_total_amount": format_currency_value(total_amount),
        "formatted_total_target": format_currency_value(total_target),
    });

    serde_json::to_string(&result).unwrap_or_else(|_| "{}".to_string())
}

/// Message data for batch operations
#[derive(Serialize, Deserialize, Clone)]
struct Message {
    id: Option<i64>,
    text: Option<String>,
    user: Option<MessageUser>,
    message_type: Option<String>,
    created_at: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
struct MessageUser {
    id: Option<i64>,
    first_name: Option<String>,
    last_name: Option<String>,
}

/// Batch-process messages: format text, compute date groups, format times
/// Input: JSON array of messages, current user ID
/// Output: JSON array with formatted fields
#[wasm_bindgen]
pub fn batch_process_messages(json_input: &str, current_user_id: i64) -> String {
    let messages: Vec<Message> = match serde_json::from_str(json_input) {
        Ok(m) => m,
        Err(_) => return "[]".to_string(),
    };

    let now_ms = js_sys::Date::now();
    let now_date = js_sys::Date::new(&JsValue::from_f64(now_ms));
    let today_str = format!("{}-{:02}-{:02}",
        now_date.get_full_year(),
        now_date.get_month() + 1,
        now_date.get_date()
    );

    let yesterday_ms = now_ms - 86_400_000.0;
    let yesterday_date = js_sys::Date::new(&JsValue::from_f64(yesterday_ms));
    let yesterday_str = format!("{}-{:02}-{:02}",
        yesterday_date.get_full_year(),
        yesterday_date.get_month() + 1,
        yesterday_date.get_date()
    );

    let mut last_date_group = String::new();
    let mut results: Vec<serde_json::Value> = Vec::with_capacity(messages.len());

    for msg in &messages {
        let text = msg.text.as_deref().unwrap_or("");
        let msg_type = msg.message_type.as_deref().unwrap_or("text");
        let is_system = msg_type == "system";

        let is_own = msg.user.as_ref()
            .and_then(|u| u.id)
            .map(|uid| uid == current_user_id)
            .unwrap_or(false);

        // Format message text (only for non-system messages)
        let formatted_text = if is_system {
            text.to_string()
        } else {
            format_message_text(text)
        };

        // Compute date group
        let date_group = if let Some(created_at) = &msg.created_at {
            let date = js_sys::Date::new(&JsValue::from_str(created_at));
            let date_str = format!("{}-{:02}-{:02}",
                date.get_full_year(),
                date.get_month() + 1,
                date.get_date()
            );
            if date_str == today_str {
                "Сегодня".to_string()
            } else if date_str == yesterday_str {
                "Вчера".to_string()
            } else {
                format_ru_date(date.get_date(), date.get_month(), date.get_full_year(),
                    now_date.get_full_year())
            }
        } else {
            String::new()
        };

        let show_date_divider = !date_group.is_empty() && date_group != last_date_group;
        if show_date_divider {
            last_date_group = date_group.clone();
        }

        // Format time
        let formatted_time = if let Some(created_at) = &msg.created_at {
            let date = js_sys::Date::new(&JsValue::from_str(created_at));
            format!("{:02}:{:02}", date.get_hours(), date.get_minutes())
        } else {
            String::new()
        };

        // Sender info
        let sender_name = if !is_own && !is_system {
            msg.user.as_ref()
                .and_then(|u| u.first_name.clone())
                .unwrap_or_default()
        } else {
            String::new()
        };

        let mut obj = serde_json::json!({
            "id": msg.id,
            "text": text,
            "formatted_text": formatted_text,
            "is_own": is_own,
            "is_system": is_system,
            "formatted_time": formatted_time,
            "sender_name": sender_name,
        });

        if show_date_divider {
            obj["date_divider"] = serde_json::json!(date_group);
        }

        results.push(obj);
    }

    serde_json::to_string(&results).unwrap_or_else(|_| "[]".to_string())
}

/// Format a Russian date string
fn format_ru_date(day: u32, month: u32, year: u32, current_year: u32) -> String {
    let month_names = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ];
    let month_name = month_names.get(month as usize).unwrap_or(&"");
    if year != current_year {
        format!("{} {} {}", day, month_name, year)
    } else {
        format!("{} {}", day, month_name)
    }
}

/// Search within messages by text content
/// Returns JSON array of matching message indices
#[wasm_bindgen]
pub fn search_messages(json_input: &str, query: &str) -> String {
    if query.trim().is_empty() {
        return "[]".to_string();
    }

    let messages: Vec<Message> = match serde_json::from_str(json_input) {
        Ok(m) => m,
        Err(_) => return "[]".to_string(),
    };

    let query_lower = query.to_lowercase();
    let results: Vec<serde_json::Value> = messages.iter().enumerate().filter_map(|(i, msg)| {
        let text = msg.text.as_deref().unwrap_or("");
        if text.to_lowercase().contains(&query_lower) {
            Some(serde_json::json!({
                "index": i,
                "id": msg.id,
            }))
        } else {
            None
        }
    }).collect();

    serde_json::to_string(&results).unwrap_or_else(|_| "[]".to_string())
}

// ──────────────────────────────────────────────
// Performance measurement utilities
// ──────────────────────────────────────────────

/// Run a performance benchmark for batch processing
/// Generates N random procurements and processes them, returning elapsed time in ms
#[wasm_bindgen]
pub fn benchmark_batch_processing(count: i32) -> f64 {
    let start = js_sys::Date::now();

    let mut procurements: Vec<serde_json::Value> = Vec::with_capacity(count as usize);
    for i in 0..count {
        procurements.push(serde_json::json!({
            "id": i,
            "title": format!("Закупка тестовая #{}", i),
            "description": format!("Описание закупки #{} для бенчмарка", i),
            "city": if i % 3 == 0 { "Москва" } else if i % 3 == 1 { "Санкт-Петербург" } else { "Новосибирск" },
            "status": if i % 4 == 0 { "active" } else if i % 4 == 1 { "draft" } else if i % 4 == 2 { "completed" } else { "payment" },
            "current_amount": (i as f64) * 150.0 + 500.0,
            "target_amount": (i as f64) * 200.0 + 10000.0,
            "deadline": "2026-12-31T23:59:59Z",
            "participant_count": (i % 50) + 1,
            "category": format!("Категория {}", i % 5),
            "organizer_name": format!("Организатор {}", i % 10),
            "created_at": "2026-01-15T10:00:00Z",
        }));
    }

    let json = serde_json::to_string(&procurements).unwrap_or_default();

    // Run batch processing
    let _ = batch_process_procurements(&json);
    let _ = search_procurements(&json, "тестовая Москва");
    let _ = sort_procurements(&json, "amount", "desc");
    let _ = aggregate_procurement_stats(&json);

    let end = js_sys::Date::now();
    end - start
}

// ──────────────────────────────────────────────
// Unit tests (run with `cargo test`)
// ──────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    // ── Validation tests ──

    #[test]
    fn test_validate_phone_valid() {
        assert!(validate_phone("+79991234567"));
        assert!(validate_phone("+7 999 123 4567"));
        assert!(validate_phone("")); // empty is valid (optional)
    }

    #[test]
    fn test_validate_phone_invalid() {
        assert!(!validate_phone("123")); // too short, no +
        assert!(!validate_phone("+123")); // too short even with +
    }

    #[test]
    fn test_validate_email_valid() {
        assert!(validate_email("user@example.com"));
        assert!(validate_email("test@mail.ru"));
        assert!(validate_email("")); // empty is valid (optional)
    }

    #[test]
    fn test_validate_email_invalid() {
        assert!(!validate_email("notanemail"));
        assert!(!validate_email("@domain.com"));
        assert!(!validate_email("user@"));
    }

    // ── Formatting tests ──

    #[test]
    fn test_calculate_progress() {
        assert_eq!(calculate_progress(500.0, 1000.0), 50);
        assert_eq!(calculate_progress(0.0, 1000.0), 0);
        assert_eq!(calculate_progress(1500.0, 1000.0), 100); // capped at 100
        assert_eq!(calculate_progress(100.0, 0.0), 0); // division by zero guard
    }

    #[test]
    fn test_format_currency() {
        assert_eq!(format_currency(1000.0), "1 000 ₽");
        assert_eq!(format_currency(0.0), "0 ₽");
        assert_eq!(format_currency(1234567.89), "1 234 567,89 ₽");
        assert_eq!(format_currency(99.5), "99,50 ₽");
    }

    #[test]
    fn test_get_avatar_color() {
        let color = get_avatar_color("Тест");
        assert!(color.starts_with('#'));
        assert_eq!(color.len(), 7); // #RRGGBB format

        // Same name should always produce same color
        assert_eq!(get_avatar_color("Иван"), get_avatar_color("Иван"));
    }

    #[test]
    fn test_get_initials() {
        assert_eq!(get_initials("Иван", "Петров"), "ИП");
        assert_eq!(get_initials("Anna", ""), "A");
        assert_eq!(get_initials("", ""), "?");
    }

    #[test]
    fn test_escape_html() {
        assert_eq!(escape_html("<script>alert('xss')</script>"),
            "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;");
        assert_eq!(escape_html("Hello & World"), "Hello &amp; World");
        assert_eq!(escape_html("\"quoted\""), "&quot;quoted&quot;");
        assert_eq!(escape_html("normal text"), "normal text");
    }

    #[test]
    fn test_format_message_text_basic() {
        assert_eq!(format_message_text(""), "");
        assert_eq!(format_message_text("Hello"), "Hello");
    }

    #[test]
    fn test_format_message_text_xss() {
        let result = format_message_text("<script>alert(1)</script>");
        assert!(!result.contains("<script>"));
        assert!(result.contains("&lt;script&gt;"));
    }

    #[test]
    fn test_format_message_text_urls() {
        let result = format_message_text("Visit https://example.com please");
        assert!(result.contains("<a href=\"https://example.com\""));
        assert!(result.contains("target=\"_blank\""));
    }

    #[test]
    fn test_format_message_text_newlines() {
        let result = format_message_text("Line 1\nLine 2");
        assert!(result.contains("<br>"));
    }

    // ── Search and sorting tests ──

    #[test]
    fn test_search_procurements() {
        let json = serde_json::json!([
            {"id": 1, "title": "Мед натуральный", "description": "Свежий мед", "city": "Москва"},
            {"id": 2, "title": "Масло оливковое", "description": "Из Греции", "city": "Санкт-Петербург"},
            {"id": 3, "title": "Чай зеленый", "description": "Японский чай", "city": "Москва"},
        ]).to_string();

        let result = search_procurements(&json, "Москва");
        let parsed: Vec<serde_json::Value> = serde_json::from_str(&result).unwrap();
        assert_eq!(parsed.len(), 2); // two procurements in Moscow

        let result_empty = search_procurements(&json, "");
        assert_eq!(result_empty, "[]");

        let result_none = search_procurements(&json, "Несуществующий");
        let parsed_none: Vec<serde_json::Value> = serde_json::from_str(&result_none).unwrap();
        assert_eq!(parsed_none.len(), 0);
    }

    #[test]
    fn test_sort_procurements() {
        let json = serde_json::json!([
            {"id": 1, "title": "Банан", "current_amount": 300.0},
            {"id": 2, "title": "Апельсин", "current_amount": 100.0},
            {"id": 3, "title": "Вишня", "current_amount": 200.0},
        ]).to_string();

        // Sort by title ascending
        let sorted = sort_procurements(&json, "title", "asc");
        let ids: Vec<i64> = serde_json::from_str(&sorted).unwrap();
        assert_eq!(ids, vec![2, 1, 3]); // Апельсин, Банан, Вишня

        // Sort by amount descending
        let sorted_desc = sort_procurements(&json, "amount", "desc");
        let ids_desc: Vec<i64> = serde_json::from_str(&sorted_desc).unwrap();
        assert_eq!(ids_desc, vec![1, 3, 2]); // 300, 200, 100
    }

    #[test]
    fn test_aggregate_procurement_stats() {
        let json = serde_json::json!([
            {"id": 1, "title": "A", "status": "active", "current_amount": 500.0, "target_amount": 1000.0, "city": "Москва", "participant_count": 5},
            {"id": 2, "title": "B", "status": "active", "current_amount": 300.0, "target_amount": 800.0, "city": "СПб", "participant_count": 3},
            {"id": 3, "title": "C", "status": "completed", "current_amount": 1000.0, "target_amount": 1000.0, "city": "Москва", "participant_count": 10},
        ]).to_string();

        let result = aggregate_procurement_stats(&json);
        let stats: serde_json::Value = serde_json::from_str(&result).unwrap();

        assert_eq!(stats["total_count"], 3);
        assert_eq!(stats["active_count"], 2);
        assert_eq!(stats["total_amount"], 1800.0);
        assert_eq!(stats["total_target"], 2800.0);
        assert_eq!(stats["cities"].as_array().unwrap().len(), 2); // Москва, СПб
    }

    #[test]
    fn test_search_messages() {
        let json = serde_json::json!([
            {"id": 1, "text": "Привет всем!"},
            {"id": 2, "text": "Когда доставка?"},
            {"id": 3, "text": "Привет! Доставка завтра"},
        ]).to_string();

        let result = search_messages(&json, "привет");
        let parsed: Vec<serde_json::Value> = serde_json::from_str(&result).unwrap();
        assert_eq!(parsed.len(), 2); // messages 1 and 3

        let result_delivery = search_messages(&json, "доставка");
        let parsed_delivery: Vec<serde_json::Value> = serde_json::from_str(&result_delivery).unwrap();
        assert_eq!(parsed_delivery.len(), 2); // messages 2 and 3
    }

    // ── Edge case tests ──

    #[test]
    fn test_empty_json_input() {
        assert_eq!(search_procurements("[]", "test"), "[]");
        assert_eq!(sort_procurements("[]", "title", "asc"), "[]");
        // Empty array returns valid stats object with zero values
        let stats: serde_json::Value = serde_json::from_str(&aggregate_procurement_stats("[]")).unwrap();
        assert_eq!(stats["total_count"], 0);
        assert_eq!(stats["active_count"], 0);
        assert_eq!(search_messages("[]", "test"), "[]");
    }

    #[test]
    fn test_invalid_json_input() {
        assert_eq!(search_procurements("not json", "test"), "[]");
        assert_eq!(sort_procurements("{bad}", "title", "asc"), "[]");
        assert_eq!(aggregate_procurement_stats("invalid"), "{}");
    }

    #[test]
    fn test_format_ru_date() {
        assert_eq!(format_ru_date(15, 0, 2026, 2026), "15 января"); // same year
        assert_eq!(format_ru_date(1, 11, 2025, 2026), "1 декабря 2025"); // different year
        assert_eq!(format_ru_date(28, 5, 2026, 2026), "28 июня"); // month index 5 = June
    }

    #[test]
    fn test_format_currency_value_internal() {
        assert_eq!(format_currency_value(0.0), "0 ₽");
        assert_eq!(format_currency_value(1234.56), "1 234,56 ₽");
        assert_eq!(format_currency_value(999999.0), "999 999 ₽");
    }
}
