from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REMOVED_PROJECTS = (
    "eventflow_backend",
    "logitrack_backend",
    "feedback-form-laravel-vue",
    "mapsoft-platform",
    "medibot_backend",
)


def test_issue_99_legacy_project_directories_are_removed():
    remaining = [project for project in REMOVED_PROJECTS if (ROOT / project).exists()]

    assert remaining == []


def test_issue_99_removed_projects_are_not_referenced_by_active_files():
    ignored_roots = {".git", ".pytest_cache", "__pycache__"}
    allowed_files = {
        Path("tests/test_issue_99_removed_legacy_projects.py"),
    }
    references = []

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if set(relative.parts) & ignored_roots:
            continue
        if relative in allowed_files:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for project in REMOVED_PROJECTS:
            if project in content:
                references.append(f"{relative}: {project}")

    assert references == []
