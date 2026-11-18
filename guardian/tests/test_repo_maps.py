import pytest

from guardian_kit.context import Repo
from guardian_kit.repo_maps import _names_repo, find_map_files, load_repo_map

POLICY = """# Technical & Engineering Policy: `org/locopy`
## 1. Document Overview
text
## 2. Technology Stack
| boto3 | `locopy/s3.py` |
## 3. Repository Architecture
| `locopy/utility.py` | File helpers: gzip, split, concatenate |
## 4. Coding Standards
| CODE-001 | lint `locopy/s3.py` |
## 5. Reusable Components and Existing Capabilities
| `compress_file`, `split_file` | File utilities | `locopy/utility.py` | gzip and N-way split |
## 7. Security Policies
| SEC-001 | never hardcode keys in `locopy/s3.py` |
"""


@pytest.fixture(autouse=True)
def _isolate_from_real_data_folder(monkeypatch, tmp_path):
    # the engine always reads <guardian>/data; keep the real policy documents out of these tests
    monkeypatch.setattr("guardian_kit.repo_maps.GUARDIAN_ROOT", tmp_path / "no-guardian-root")


def test_policy_file_is_matched_to_its_repo_by_name():
    assert _names_repo("capitalone-locopy_technical_policy", "locopy")
    assert _names_repo("capitalone-rubicon-ml_technical_policy", "rubicon-ml")
    assert _names_repo("capitalone-DataProfiler_technical_policy", "dataprofiler")
    assert not _names_repo("capitalone-locopy2_technical_policy", "locopy")


def test_data_folder_docs_are_found_and_only_descriptive_sections_are_read(tmp_path):
    ctx = tmp_path / "context"
    repo = ctx / "repos" / "locopy"
    (repo / "locopy").mkdir(parents=True)
    for f in ("utility.py", "s3.py"):
        (repo / "locopy" / f).write_text("x = 1\n")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "org-locopy_technical_policy.md").write_text(POLICY)
    (tmp_path / "data" / "org-other_technical_policy.md").write_text(POLICY)

    files, weak = find_map_files(ctx, Repo("locopy", repo))
    assert [f.name for f in files] == ["org-locopy_technical_policy.md"] and not weak

    rmap = load_repo_map(ctx, Repo("locopy", repo), ["locopy/utility.py", "locopy/s3.py"])
    assert any("gzip" in n for n in rmap.file_notes["locopy/utility.py"])
    assert "compress_file" in rmap.symbol_notes and "split_file" in rmap.symbol_notes
    # stack, coding-standard and security lines must not describe s3.py
    assert "locopy/s3.py" not in rmap.file_notes


def test_short_breakdown_files_are_read_in_full(tmp_path):
    ctx = tmp_path / "context"
    repo = ctx / "repos" / "r"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "pay.py").write_text("x = 1\n")
    (ctx / "repos" / "r.md").write_text("# r\n## Security\n| `src/pay.py` | signs payment requests |\n")
    rmap = load_repo_map(ctx, Repo("r", repo), ["src/pay.py"])
    assert rmap.file_notes["src/pay.py"] == ["signs payment requests"]
