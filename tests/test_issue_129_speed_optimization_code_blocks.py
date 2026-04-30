from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "speed-optimization" / "implementation-code-blocks.md"


def read_doc() -> str:
    assert DOC.is_file(), (
        "Issue #129 asks for concrete code blocks in speed-optimization. "
        f"Missing {DOC.relative_to(ROOT)}."
    )
    return DOC.read_text(encoding="utf-8")


def test_code_block_guide_exists_in_speed_optimization():
    text = read_doc()
    assert "# Блоки кода для оптимизации скорости" in text


def test_guide_contains_enough_fenced_code_blocks():
    text = read_doc()
    assert text.count("```") >= 24, (
        "The guide must contain concrete fenced code blocks for the requested "
        "optimization changes, not only prose."
    )


def test_guide_covers_report_quick_wins_and_high_impact_areas():
    text = read_doc()
    required_fragments = [
        "CookieConsentManager.php",
        "database/migrations",
        "PruneCookieConsents.php",
        "ItemRepository.php",
        "FastSearch.php",
        "HomeController.php",
        "Price/Index.php",
        "vite.config.js",
        "nginx",
        "Cache-Control",
        "APP_DEBUG=false",
        "Redis",
        "whereFullText",
        "chunkById",
        "streamDownload",
        "EXPLAIN ANALYZE",
    ]

    missing = [fragment for fragment in required_fragments if fragment not in text]
    assert not missing, f"Missing expected implementation fragments: {missing}"
