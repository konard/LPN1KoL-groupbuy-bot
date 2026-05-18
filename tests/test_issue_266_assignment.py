from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ISSUE_DIR = ROOT / "examples" / "issue-266"
LARAVEL_DIR = ISSUE_DIR / "laravel"


def read(path):
    return path.read_text(encoding="utf-8")


def test_assignment_files_are_present():
    expected = [
        ISSUE_DIR / "README.md",
        ISSUE_DIR / "type-field-filter.js",
        LARAVEL_DIR / "composer.json",
        LARAVEL_DIR / "artisan",
        LARAVEL_DIR / "app" / "Console" / "Commands" / "FetchApiRecordCommand.php",
        LARAVEL_DIR / "app" / "Http" / "Controllers" / "ApiRecordController.php",
        LARAVEL_DIR / "app" / "Http" / "Controllers" / "VisitorController.php",
        LARAVEL_DIR / "app" / "Http" / "Controllers" / "StatsController.php",
        LARAVEL_DIR / "app" / "Http" / "Middleware" / "StatsAuth.php",
        LARAVEL_DIR / "app" / "Models" / "ExternalApiRecord.php",
        LARAVEL_DIR / "app" / "Models" / "Visit.php",
        LARAVEL_DIR / "database" / "migrations" / "2026_05_18_000001_create_external_api_records_table.php",
        LARAVEL_DIR / "database" / "migrations" / "2026_05_18_000002_create_visits_table.php",
        LARAVEL_DIR / "public" / "js" / "visitor-counter.js",
        LARAVEL_DIR / "resources" / "views" / "stats.blade.php",
        LARAVEL_DIR / "resources" / "views" / "stats-login.blade.php",
        LARAVEL_DIR / "routes" / "api.php",
        LARAVEL_DIR / "routes" / "console.php",
        LARAVEL_DIR / "routes" / "web.php",
    ]

    missing = [str(path.relative_to(ROOT)) for path in expected if not path.exists()]

    assert missing == []


def test_laravel_api_collector_is_scheduled_and_exposed_as_json():
    command = read(LARAVEL_DIR / "app" / "Console" / "Commands" / "FetchApiRecordCommand.php")
    schedule = read(LARAVEL_DIR / "routes" / "console.php")
    model = read(LARAVEL_DIR / "app" / "Models" / "ExternalApiRecord.php")
    migration = read(LARAVEL_DIR / "database" / "migrations" / "2026_05_18_000001_create_external_api_records_table.php")
    routes = read(LARAVEL_DIR / "routes" / "api.php")
    controller = read(LARAVEL_DIR / "app" / "Http" / "Controllers" / "ApiRecordController.php")
    services = read(LARAVEL_DIR / "config" / "services.php")

    assert "Http::" in command
    assert "ExternalApiRecord::create" in command
    assert "api-records:fetch" in command
    assert "everyFiveMinutes()" in schedule
    assert "external_api_records" in migration
    assert "protected $fillable" in model
    assert "Route::get('/api-records'" in routes
    assert "response()->json" in controller
    assert "official-joke-api.appspot.com" in services


def test_type_field_filter_uses_selected_value_as_name_substring():
    source = read(ISSUE_DIR / "type-field-filter.js")
    readme = read(ISSUE_DIR / "README.md")

    assert "select[name=\"type_val\"]" in source
    assert "name.includes(value)" in source
    assert "field === typeField" in source
    assert ".closest(" in source
    assert "addEventListener(\"change\"" in source
    assert "Алгоритмы" in readme
    assert "jQuery" in readme


def test_visitor_counter_client_collects_ip_city_device_and_sends_payload():
    source = read(LARAVEL_DIR / "public" / "js" / "visitor-counter.js")

    assert "ipapi.co" in source
    assert "localStorage" in source
    assert "visitor_id" in source
    assert "city" in source
    assert "device" in source
    assert "page_url" in source
    assert "navigator.sendBeacon" in source
    assert "fetch(endpoint" in source
    assert "data-endpoint" in source


def test_visitor_counter_backend_stores_visits_and_renders_authenticated_charts():
    visitor_controller = read(LARAVEL_DIR / "app" / "Http" / "Controllers" / "VisitorController.php")
    stats_controller = read(LARAVEL_DIR / "app" / "Http" / "Controllers" / "StatsController.php")
    middleware = read(LARAVEL_DIR / "app" / "Http" / "Middleware" / "StatsAuth.php")
    migration = read(LARAVEL_DIR / "database" / "migrations" / "2026_05_18_000002_create_visits_table.php")
    view = read(LARAVEL_DIR / "resources" / "views" / "stats.blade.php")
    routes = read(LARAVEL_DIR / "routes" / "web.php")

    assert "Visit::create" in visitor_controller
    assert "visitor_id" in migration
    assert "visited_at" in migration
    assert "COUNT(DISTINCT visitor_id)" in stats_controller
    assert "groupBy('hour')" in stats_controller
    assert "groupBy('city')" in stats_controller
    assert "visitor_stats_authorized" in middleware
    assert "Chart" in view
    assert "stats/login" in routes
