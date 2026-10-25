from blobbylib.naming import normalize_svg_name, plan_imports


def test_fixes_typos_and_case():
    assert normalize_svg_name("bobbly-captain.svg") == "blobby-captain"
    assert normalize_svg_name("bloby-nutcracker.svg") == "blobby-nutcracker"
    assert normalize_svg_name("Blobby.svg") == "blobby"


def test_strips_spaces_and_version_suffix():
    assert normalize_svg_name("bobbly-professor vs.2.svg") == "blobby-professor"
    assert normalize_svg_name("Dynamic Blobby.svg") == "dynamic-blobby"
    assert normalize_svg_name("Blobby=Puppy Eyes.svg") == "blobby-puppy-eyes"


def test_keeps_numbered_variants():
    assert normalize_svg_name("blobby-paris-3.svg") == "blobby-paris-3"


def test_plan_imports_uses_renames_and_reports_collisions():
    mapping, problems = plan_imports(
        ["Group 2147234011.svg", "bobbly-shine.svg", "blobby-shine.svg"],
        {"Group 2147234011.svg": "blobby-drummer"},
    )
    assert mapping["Group 2147234011.svg"] == "blobby-drummer"
    assert any("blobby-shine" in p for p in problems)


def test_unmapped_group_file_is_a_problem():
    mapping, problems = plan_imports(["Group 4.svg"], {})
    assert "Group 4.svg" not in mapping
    assert problems and "Group 4.svg" in problems[0]
