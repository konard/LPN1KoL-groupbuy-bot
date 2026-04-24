import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


PROJECTS = {
    "eventflow_backend": {
        "files": [
            ".env.example",
            "Dockerfile",
            "README.md",
            "docker-compose.yml",
            "requirements.txt",
            "app/__init__.py",
            "app/cache.py",
            "app/config.py",
            "app/database.py",
            "app/main.py",
            "app/models.py",
            "app/schemas.py",
            "app/stripe_mock.py",
            "app/tasks.py",
        ],
        "snippets": {
            "requirements.txt": ["fastapi", "celery", "asyncpg", "redis"],
            "docker-compose.yml": ["postgres", "redis", "rabbitmq", "worker"],
            "app/main.py": [
                '@app.post("/events"',
                '"/tickets/purchase"',
                "RedisEventCache",
            ],
            "app/tasks.py": ["Celery", "generate_ticket", "ticket"],
            "app/stripe_mock.py": ["4242424242424242"],
        },
    },
    "logitrack_backend": {
        "files": [
            ".env.example",
            "Dockerfile",
            "README.md",
            "docker-compose.yml",
            "requirements.txt",
            "app/__init__.py",
            "app/config.py",
            "app/database.py",
            "app/graphql_schema.py",
            "app/main.py",
            "app/models.py",
            "app/schemas.py",
            "app/tracking.py",
        ],
        "snippets": {
            "requirements.txt": ["fastapi", "strawberry-graphql", "asyncpg", "redis"],
            "docker-compose.yml": ["postgres", "redis"],
            "app/main.py": [
                '@app.websocket("/ws/orders/{order_id}"',
                '@app.post("/orders"',
                '@app.post("/orders/{order_id}/courier"',
            ],
            "app/graphql_schema.py": ["order_history", "strawberry.type"],
            "app/tracking.py": ["asyncio.sleep(2)", "set_latest_coordinates"],
        },
    },
    "medibot_backend": {
        "files": [
            ".env.example",
            "Dockerfile",
            "README.md",
            "docker-compose.yml",
            "requirements.txt",
            "app/__init__.py",
            "app/bot.py",
            "app/calendar_client.py",
            "app/config.py",
            "app/database.py",
            "app/main.py",
            "app/models.py",
            "app/tasks.py",
        ],
        "snippets": {
            "requirements.txt": ["python-telegram-bot", "celery", "asyncpg", "redis"],
            "docker-compose.yml": ["postgres", "redis", "rabbitmq", "worker"],
            "app/bot.py": ["/appointment", "CommandHandler", "RedisStateStore"],
            "app/calendar_client.py": ["create_event", "GoogleCalendar"],
            "app/tasks.py": ["send_appointment_reminder", "Celery"],
        },
    },
}


def read(project: str, path: str) -> str:
    return (ROOT / project / path).read_text(encoding="utf-8")


def test_issue_91_required_demo_project_files_exist():
    missing = []

    for project, config in PROJECTS.items():
        for path in config["files"]:
            if not (ROOT / project / path).is_file():
                missing.append(f"{project}/{path}")

    assert missing == []


def test_issue_91_demo_projects_include_requested_integrations():
    missing = []

    for project, config in PROJECTS.items():
        for path, snippets in config["snippets"].items():
            content = read(project, path)
            for snippet in snippets:
                if snippet not in content:
                    missing.append(f"{project}/{path}: {snippet}")

    assert missing == []


def test_issue_91_python_files_are_valid_and_avoid_inline_comments():
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
