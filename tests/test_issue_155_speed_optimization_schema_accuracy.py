from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "speed-optimization" / "optimization-report.md"
GUIDE = ROOT / "speed-optimization" / "implementation-code-blocks.md"


def read_docs() -> str:
    assert REPORT.is_file(), f"Missing {REPORT.relative_to(ROOT)}"
    assert GUIDE.is_file(), f"Missing {GUIDE.relative_to(ROOT)}"
    return "\n".join(
        [
            REPORT.read_text(encoding="utf-8"),
            GUIDE.read_text(encoding="utf-8"),
        ]
    )


def test_speed_optimization_docs_are_aligned_with_issue_155_sql_dump():
    text = read_docs()

    required_fragments = [
        "`cookie_consents.token`",
        "`cookie_consents(status, date)`",
        "`item_price_type` 822 549",
        "`items` 22 337",
        "`items_name_synonyms_fulltext`",
        "`category_uuid`",
        "`item_uuid`",
        "`amount_item`",
        "в дампе нет `items.in_archive`",
    ]

    missing = [fragment for fragment in required_fragments if fragment not in text]
    assert not missing, f"Docs should cite real SQL-dump schema details: {missing}"


def test_speed_optimization_code_blocks_do_not_recommend_nonexistent_columns():
    text = read_docs()

    stale_fragments = [
        "identifier",
        "export_archived",
        "activePrice",
        "availableAmount",
        "firstImage",
        "old_price",
        "'slug'",
        '"slug"',
        "item_id,path",
    ]

    present = [fragment for fragment in stale_fragments if fragment in text]
    assert not present, f"Docs still contain stale schema assumptions: {present}"
