import importlib.util
from pathlib import Path
from types import SimpleNamespace

BOOTSTRAP_PATH = Path(__file__).resolve().parents[1] / "deploy" / "readweave_bootstrap.py"
BOOTSTRAP_SPEC = importlib.util.spec_from_file_location("readweave_bootstrap", BOOTSTRAP_PATH)
readweave_bootstrap = importlib.util.module_from_spec(BOOTSTRAP_SPEC)
BOOTSTRAP_SPEC.loader.exec_module(readweave_bootstrap)


def test_build_uses_absolute_dockerfile_from_unpacked_source(tmp_path, monkeypatch):
    source_root = tmp_path / "unpacked-source"
    source_root.mkdir()
    caller_root = tmp_path / "caller"
    caller_root.mkdir()
    monkeypatch.chdir(caller_root)

    commands = []

    def capture_run(args, capture=True):
        commands.append(args)
        if args[:2] == ["docker", "build"]:
            dockerfile = Path(args[args.index("--file") + 1])
            assert dockerfile.is_absolute()
            assert dockerfile.is_relative_to(source_root)
            assert dockerfile.is_file()
            return ""
        return ""

    monkeypatch.setattr(
        readweave_bootstrap.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=""),
    )
    monkeypatch.setattr(readweave_bootstrap, "run", capture_run)
    monkeypatch.setattr(readweave_bootstrap, "managed_container_url", lambda: None)
    monkeypatch.setattr(readweave_bootstrap, "ensure_named_volume", lambda: None)
    monkeypatch.setattr(readweave_bootstrap, "health_check", lambda _url: None)

    url = readweave_bootstrap.build_and_start(source_root, "a" * 64, 8765)

    assert url == "http://127.0.0.1:8765"
    dockerfile = (source_root / ".lessonweave-readweave.Dockerfile").read_text(encoding="utf-8")
    assert "COPY --from=runtime-dependencies /usr/src/app/build/node_modules/better-sqlite3" in dockerfile
    assert any(command[:2] == ["docker", "build"] for command in commands)
