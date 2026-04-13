use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;

pub async fn create_pool(database_url: &str) -> Result<PgPool, sqlx::Error> {
    const MAX_RETRIES: u32 = 10;
    const RETRY_DELAY_SECS: u64 = 3;

    let mut last_err = None;
    for attempt in 1..=MAX_RETRIES {
        match PgPoolOptions::new()
            .max_connections(10)
            .acquire_timeout(std::time::Duration::from_secs(5))
            .connect(database_url)
            .await
        {
            Ok(pool) => return Ok(pool),
            Err(e) => {
                tracing::warn!(
                    "Database connection attempt {}/{} failed: {}. Retrying in {}s...",
                    attempt,
                    MAX_RETRIES,
                    e,
                    RETRY_DELAY_SECS
                );
                last_err = Some(e);
                tokio::time::sleep(std::time::Duration::from_secs(RETRY_DELAY_SECS)).await;
            }
        }
    }
    Err(last_err.unwrap())
}

pub async fn run_migrations(pool: &PgPool) -> Result<(), sqlx::Error> {
    let migration_sql = include_str!("../../migrations/001_initial.sql");
    sqlx::raw_sql(migration_sql).execute(pool).await?;

    let migration_002 = include_str!("../../migrations/002_add_selfie_file_id.sql");
    sqlx::raw_sql(migration_002).execute(pool).await?;

    let migration_003 = include_str!("../../migrations/003_widen_phone_and_language_code.sql");
    sqlx::raw_sql(migration_003).execute(pool).await?;

    tracing::info!("Database migrations applied successfully");
    Ok(())
}
