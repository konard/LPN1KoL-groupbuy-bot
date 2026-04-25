import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


PROJECTS = ("eventflow_backend", "logitrack_backend", "medibot_backend")


def read(project: str, path: str) -> str:
    return (ROOT / project / path).read_text(encoding="utf-8")


def test_issue_97_projects_include_middle_backend_files():
    missing = []

    for project in PROJECTS:
        for path in (
            "alembic.ini",
            "migrations/__init__.py",
            "migrations/env.py",
            "migrations/script.py.mako",
            "migrations/versions/0001_initial.py",
        ):
            if not (ROOT / project / path).is_file():
                missing.append(f"{project}/{path}")

    assert missing == []


def test_issue_97_shared_practices_are_present():
    checks = {
        "eventflow_backend": {
            "requirements.txt": ["PyJWT", "structlog", "alembic"],
            ".env.example": ["JWT_SECRET_KEY", "RATE_LIMIT_MAX_REQUESTS"],
            "README.md": ["alembic upgrade head", "pytest", "/health"],
            "app/main.py": [
                "@app.exception_handler",
                "get_current_actor",
                "require_role",
                "rate_limit",
                '@app.get("/health"',
                "date_from",
                "page:",
            ],
            "app/schemas.py": ["json_schema_extra", "examples"],
        },
        "logitrack_backend": {
            "requirements.txt": ["structlog", "alembic"],
            ".env.example": ["API_TOKEN", "RATE_LIMIT_MAX_REQUESTS"],
            "README.md": ["alembic upgrade head", "pytest", "/health"],
            "app/main.py": [
                "require_api_token",
                "rate_limit",
                '@app.get("/health"',
                "websocket.query_params",
            ],
            "app/graphql_schema.py": ["GeoJSONPoint", "GeoJSONFeature", "track"],
        },
        "medibot_backend": {
            "requirements.txt": ["structlog", "alembic"],
            ".env.example": ["RATE_LIMIT_MAX_REQUESTS"],
            "README.md": ["alembic upgrade head", "pytest"],
            "app/bot.py": [
                "ConversationHandler",
                "CallbackQueryHandler",
                "InlineKeyboardButton",
                "appointments",
                "check_rate_limit",
            ],
            "app/calendar_client.py": ["ABC", "abstractmethod", "GoogleCalendarClient"],
        },
    }
    missing = []

    for project, files in checks.items():
        for path, snippets in files.items():
            content = read(project, path)
            for snippet in snippets:
                if snippet not in content:
                    missing.append(f"{project}/{path}: {snippet}")

    assert missing == []


def test_issue_97_specific_features_are_present():
    checks = {
        "eventflow_backend/app/main.py": [
            '@app.post("/tickets/{ticket_id}/return"',
            "return_ticket_task.apply_async",
            "HTTPException",
        ],
        "eventflow_backend/app/tasks.py": ["return_ticket_task", "ticket.status ="],
        "logitrack_backend/app/tracking.py": [
            "asyncio.CancelledError",
            "GeoJSON",
            "set_latest_coordinates",
        ],
        "medibot_backend/app/bot.py": [
            "InlineKeyboardMarkup",
            "select_clinic",
            "select_time",
            "list_appointments",
            "send_appointment_reminder.apply_async",
        ],
    }
    missing = []

    for path, snippets in checks.items():
        content = (ROOT / path).read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in content:
                missing.append(f"{path}: {snippet}")

    assert missing == []


def test_issue_97_python_files_parse_and_keep_code_comment_free():
    failures = []

    for project in PROJECTS:
        for path in (ROOT / project / "app").glob("*.py"):
            content = path.read_text(encoding="utf-8")
            ast.parse(content, filename=str(path))
            comment_lines = [
                line_number
                for line_number, line in enumerate(content.splitlines(), start=1)
                if line.lstrip().startswith("#")
            ]
            if comment_lines:
                failures.append(f"{path.relative_to(ROOT)}:{comment_lines[0]}")

    assert failures == []
