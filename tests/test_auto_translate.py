import ast
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "auto_translate.py"


def load_auto_translate_module():
    module = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    kept_nodes = []
    for node in module.body:
        if isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id == "DEFAULT_BROWSER_HEADERS":
                    kept_nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in {
            "_browser_headers",
            "get_request_session",
            "send_request",
            "get_google_translation",
            "convert",
            "get_last_release_content",
        }:
            kept_nodes.append(node)

    namespace = {
        "requests": __import__("requests"),
        "cloudscraper": None,
        "curl_requests": None,
        "subprocess": __import__("subprocess"),
    }
    exec(compile(ast.Module(body=kept_nodes, type_ignores=[]), str(SCRIPT_PATH), "exec"), namespace)
    return namespace


def test_get_google_translation_handles_throttle_response():
    module = load_auto_translate_module()

    class FakeResponse:
        status_code = 429
        text = "<html>Sorry...</html>"

        def json(self):
            raise ValueError("not json")

    module["send_request"] = lambda *args, **kwargs: FakeResponse()

    assert module["get_google_translation"]("it", "Drying filament") is None


def test_convert_keeps_existing_translations_when_google_throttles():
    module = load_auto_translate_module()

    class FakeResponse:
        status_code = 429
        text = "<html>Sorry...</html>"

        def json(self):
            raise ValueError("not json")

    module["send_request"] = lambda *args, **kwargs: FakeResponse()

    target = {"drying": "Asciugatura"}
    old_source = {"drying": "Old string"}
    new_source = {"drying": "Drying filament"}

    module["convert"](old_source, new_source, target, "it")

    assert target == {"drying": "Asciugatura"}


def test_get_last_release_content_uses_repo_relative_path(monkeypatch):
    module = load_auto_translate_module()
    calls = []

    class FakeCompleted:
        returncode = 0
        stdout = '{"device_automation": {}}'

    def fake_run(args, capture_output, text):
        calls.append(args)
        return FakeCompleted()

    monkeypatch.setattr(module["subprocess"], "run", fake_run)

    assert module["get_last_release_content"]() == '{"device_automation": {}}'
    assert calls and calls[0][1] == "custom_components/bambu_lab/translations/en.json"
