import io
import json

from guardian_kit import live


def _ev(**kw):
    return json.dumps(kw) + "\n"


def test_live_renders_progress_then_result(tmp_path):
    stream = io.StringIO(
        _ev(type="assistant", message={"content": [{"type": "tool_use", "name": "Bash", "input": {
            "command": "./bin/guardian blueprint --format json --expand 'upload=put_object,s3' - <<'X'"}}]})
        + _ev(type="assistant", message={"content": [{"type": "tool_use", "name": "Read", "input": {
            "file_path": "/x/context/repos/locopy/locopy/s3.py", "offset": 183, "limit": 40}}]})
        + "not json\n"
        + _ev(type="result", subtype="success", result="## Blueprint: t\n### Reuse directly\n1. `upload_to_s3`",
              total_cost_usd=0.25)
    )
    lines = []
    out = tmp_path / "live.md"
    assert live.run(stream, out, "💡 Code recommendation", "Export mismatches", "sonnet", echo=lines.append) == 0
    page = out.read_text()
    assert page.startswith("# 💡 Code recommendation") and "`upload_to_s3`" in page and "$0.25" in page
    assert any("put_object" in line for line in lines)  # identifiers keep their underscores
    assert any("locopy/locopy/s3.py (lines 183-223)" in line for line in lines)


def test_live_reports_a_missing_result(tmp_path):
    out = tmp_path / "live.md"
    assert live.run(io.StringIO(""), out, "t", "s", "m", echo=lambda s: None) == 1
    assert "without a result" in out.read_text()
