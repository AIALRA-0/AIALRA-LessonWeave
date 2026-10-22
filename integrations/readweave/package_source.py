"""从 Git 当前版本和经过哈希校验的增量文件清单生成可复现的公开源码包。"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


PACKAGE_ROOT_NAME = "readweave-source"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OVERLAY_MANIFEST = SCRIPT_DIR / "backend-source-manifest.json"
ROOT_FILES = {
    "LICENSE",
    "NOTICE",
    "CODE_OF_CONDUCT",
    "contributors.json",
    "SECURITY.md",
    ".nvmrc",
    ".npmrc",
    ".pnpmfile.cjs",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "tsconfig.base.json",
    "tsconfig.json",
    "eslint.config.mjs",
    "eslint.format.config.mjs",
    "vitest.config.ts",
}
WORKSPACE_MANIFEST_ROOTS = {"apps", "packages"}
SOURCE_ROOTS = {"apps", "packages", "assets", "scripts", "patches"}
BUILD_SUPPORT_FILES = {
    "packages/trilium-core/src/test/becca_easy_mocking.ts",
    "packages/trilium-core/src/test/becca_mocking.ts",
}
RUNTIME_SUPPORT_FILES = {
    "apps/server/docker/package.json",
    "apps/server/docker/pnpm-workspace.yaml",
    "apps/server/src/assets/llm/prompts/base_system_prompt.md",
    "apps/server/src/assets/llm/prompts/providers/anthropic_tool_prompt.md",
    "apps/server/src/assets/llm/prompts/providers/ollama_tool_prompt.md",
    "apps/server/src/assets/llm/prompts/providers/openai_tool_prompt.md",
    "apps/server/src/assets/llm/skills/backend_scripting.md",
    "apps/server/src/assets/llm/skills/dashboards.md",
    "apps/server/src/assets/llm/skills/frontend_scripting.md",
    "apps/server/src/assets/llm/skills/search_syntax.md",
    "apps/server/src/assets/readweave-writing-skill/SKILL.md",
    "apps/server/src/assets/readweave-writing-skill/references/aemp-content-sufficiency.md",
    "apps/server/src/assets/readweave-writing-skill/references/apcf-style-v0.1.md",
    "apps/server/src/assets/readweave-writing-skill/references/apcf-writing-v0.1.md",
    "apps/server/src/assets/readweave-writing-skill/references/complex-reports.md",
    "apps/server/src/assets/readweave-writing-skill/references/composition.md",
    "apps/server/src/assets/readweave-writing-skill/references/explanation-framework.md",
    "apps/server/src/assets/readweave-writing-skill/references/format-rules.md",
    "apps/server/src/assets/readweave-writing-skill/references/formula-explanation.md",
    "apps/server/src/assets/readweave-writing-skill/references/local-review.md",
    "apps/server/src/assets/readweave-writing-skill/references/natural-chinese.md",
    "apps/server/src/assets/readweave-writing-skill/references/quality-development.md",
    "apps/server/src/assets/readweave-writing-skill/references/structured-documents.md",
    "apps/server/src/assets/readweave-writing-skill/references/style-rules.md",
    "apps/server/src/assets/readweave-writing-skill/references/technical-content.md",
}
FORBIDDEN_COMPONENTS = {
    ".agent-project-control",
    ".cache",
    ".claude",
    ".codex",
    ".git",
    ".github",
    ".gitlab",
    ".private",
    ".vscode",
    "coverage",
    "deploy",
    "docs",
    "documentation",
    "evals",
    "node_modules",
    "output",
    "test-output",
}
FORBIDDEN_NAMES = {
    "active-browser-plan.log",
    "active-browser-test.log",
    "agents.md",
    "apcf-start.md",
    "claude.md",
    "codex_continuation_prompt.md",
    "current.md",
    "readme.md",
    "readme.en.md",
    "readme_readweave.md",
    "readme.md.apcf-meta.yaml",
    "readme.en.md.apcf-meta.yaml",
}
FORBIDDEN_SUFFIXES = {
    ".age",
    ".bak",
    ".cer",
    ".crt",
    ".db",
    ".enc",
    ".key",
    ".log",
    ".map",
    ".p12",
    ".pfx",
    ".pem",
    ".sqlite",
    ".sqlite3",
    ".tsbuildinfo",
}
ALLOWED_NPMRC_KEYS = {
    "auto-install-peers",
    "link-workspace-packages",
    "node-linker",
    "resolution-mode",
    "save-prefix",
    "shared-workspace-lockfile",
    "strict-peer-dependencies",
    "workspace-concurrency",
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"(?i)https?://[^\s/@:]+:[^\s/@]+@"),
)
ABSOLUTE_USER_PATH_PATTERNS = (
    re.compile(r"(?i)\b[A-Z]:[\\/](?:Users|Documents and Settings|AIALRA)[\\/][^\s\"'<>]+"),
    re.compile(r"(?:^|[\s\"'])/(?:Users|home)/[^/\s\"'<>]+/[^/\s\"'<>]+(?:/[^\s\"'<>]*)?"),
)
DOCUMENTATION_AUTH_URL = re.compile(r"https?://([^:/\s]+):([^/@\s]+)@")
PLACEHOLDER_USER_PARTS = {"user", "username", "example"}
PLACEHOLDER_PASSWORD_PARTS = {"pass", "password", "example"}


class PackageError(RuntimeError):
    """当输入源码无法按固定规则安全、可复现地打包时使用。"""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _safe_repo_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or re.match(r"^[A-Za-z]:/", value):
        raise PackageError(f"overlay 路径必须是非空的仓库相对 POSIX 路径: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PackageError(f"overlay 路径越出源码仓库: {value!r}")
    normalized = path.as_posix()
    if normalized != value:
        raise PackageError(f"overlay 路径格式不规范: {value!r}")
    return normalized


def _is_forbidden_path(path: str, *, allow_overlay_test: bool = False) -> bool:
    parts = PurePosixPath(path).parts
    lowered = [part.casefold() for part in parts]
    if any(part in FORBIDDEN_COMPONENTS for part in lowered):
        return True
    name = lowered[-1]
    if name.startswith("dockerfile") or name.startswith("docker-compose") or name in {"compose.yml", "compose.yaml"}:
        return True
    if (
        any(part in {"docker", "kubernetes", "helm", "terraform", "infra"} for part in lowered)
        and path not in RUNTIME_SUPPORT_FILES
    ):
        return True
    if name in FORBIDDEN_NAMES:
        return True
    if name.startswith(".env") or name in {".npmrc.auth", "credentials", "secrets.json"}:
        return True
    if any(name.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
        return True
    if (
        name.endswith((".md", ".rst", ".adoc"))
        and path not in RUNTIME_SUPPORT_FILES
        and not re.search(r"(?:license|licence|notice)", name)
    ):
        return True
    if not allow_overlay_test:
        if name.endswith((".spec.ts", ".spec.tsx", ".test.ts", ".test.tsx", ".test.js", ".test.jsx")):
            return True
        if any(part in {"__tests__", "test", "tests", "testdata", "fixtures", "playwright-report"} for part in lowered):
            return True
    if name.endswith(".patch") and path.startswith("scripts/readweave/"):
        return True
    return False


def _is_workspace_manifest(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return len(parts) == 3 and parts[0] in WORKSPACE_MANIFEST_ROOTS and parts[-1] == "package.json"


def _base_include(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if len(parts) == 1:
        return parts[0] in ROOT_FILES
    if parts[0] not in SOURCE_ROOTS:
        return False
    if parts[0] == "apps":
        if len(parts) >= 2 and parts[1] in {"client", "server"}:
            return True
        return _is_workspace_manifest(path)
    if parts[0] == "packages" and len(parts) >= 2 and parts[1] == "trilium-e2e":
        return _is_workspace_manifest(path)
    if parts[0] == "scripts":
        return not (len(parts) > 1 and parts[1] in {"readweave", "repo-migration"})
    return True


def _should_include(path: str, overlay_paths: set[str]) -> bool:
    if _is_forbidden_path(
        path,
        allow_overlay_test=path in overlay_paths or path in BUILD_SUPPORT_FILES,
    ):
        return False
    if path in overlay_paths:
        return True
    return _base_include(path)


def _read_overlay_manifest(path: Path, commit: str) -> tuple[list[dict[str, Any]], set[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"无法读取 overlay manifest: {path.name}") from exc
    if not isinstance(value, dict):
        raise PackageError("overlay manifest 顶层必须是对象")
    if value.get("schema_version") != 1:
        raise PackageError("overlay manifest schema_version 必须为 1")
    baseline_ref = value.get("baseline_ref")
    if not isinstance(baseline_ref, str) or len(baseline_ref) < 10 or not commit.startswith(baseline_ref):
        raise PackageError("当前 HEAD 与 overlay manifest 的 baseline_ref 不一致")
    if value.get("license") != "AGPL-3.0-only":
        raise PackageError("overlay manifest 的许可证标识不是 AGPL-3.0-only")
    files = value.get("files")
    if not isinstance(files, list) or not files:
        raise PackageError("overlay manifest 必须列出 files")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise PackageError("overlay manifest 的每个 files 项必须是对象")
        relative = _safe_repo_path(item.get("path"))
        expected_hash = item.get("sha256")
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise PackageError(f"overlay manifest 中的 SHA-256 格式无效: {relative}")
        if "test" in item and not isinstance(item["test"], bool):
            raise PackageError(f"overlay manifest 的 test 字段必须是布尔值: {relative}")
        if relative in seen:
            raise PackageError(f"overlay manifest 重复列出文件: {relative}")
        is_test = bool(item.get("test", False))
        if _is_forbidden_path(relative, allow_overlay_test=is_test) or not _base_include(relative):
            raise PackageError(f"overlay 文件不属于允许打包的源码范围: {relative}")
        seen.add(relative)
        normalized.append({"path": relative, "sha256": expected_hash, "test": is_test})
    return normalized, seen


def _git_commit(source: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PackageError("--source 必须指向一个可读取 HEAD 的 Git 仓库") from exc
    return result.stdout.strip()


def _archive_head(source: Path, archive_path: Path) -> None:
    try:
        with archive_path.open("wb") as output:
            subprocess.run(
                ["git", "-C", str(source), "-c", "core.autocrlf=false", "archive", "--format=tar", "HEAD"],
                check=True,
                stdout=output,
                stderr=subprocess.PIPE,
            )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PackageError("git archive HEAD 读取失败") from exc


def _safe_target(stage: Path, relative: str) -> Path:
    target = stage.joinpath(*PurePosixPath(relative).parts)
    resolved_stage = stage.resolve()
    resolved_target = target.resolve()
    if resolved_target != resolved_stage and resolved_stage not in resolved_target.parents:
        raise PackageError(f"源码路径越出临时打包目录: {relative}")
    return target


def _read_tar_member(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    if not member.isfile():
        raise PackageError(f"Git 基线含有非普通文件，拒绝打包: {member.name}")
    stream = archive.extractfile(member)
    if stream is None:
        raise PackageError(f"无法读取 Git 基线文件: {member.name}")
    with stream:
        return stream.read()


def _sanitize_package_json(relative: str, data: bytes) -> tuple[bytes, list[str]]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"package.json 不是有效 UTF-8 JSON: {relative}") from exc
    actions: list[str] = []
    author = value.get("author")
    if isinstance(author, dict) and "email" in author:
        author.pop("email", None)
        actions.append("author_email_removed")
    elif isinstance(author, str):
        sanitized = re.sub(r"\s*<[^<>\s]+@[^<>\s]+>", "", author).strip()
        if sanitized != author:
            value["author"] = sanitized
            actions.append("author_email_removed")
    if "maintainers" in value:
        value.pop("maintainers", None)
        actions.append("maintainer_contacts_removed")
    if relative == "package.json":
        scripts = value.get("scripts")
        kept = {
            key: scripts[key]
            for key in ("client:build", "server:build")
            if isinstance(scripts, dict) and key in scripts
        }
        if scripts != kept:
            value["scripts"] = kept
            actions.append("root_build_scripts_only")
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), actions


def _sanitize_contributors(data: bytes) -> tuple[bytes, list[str]]:
    # About 面板构建时需要导入这份清单；打包时只保留空列表，避免公开贡献者姓名和个人链接。
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PackageError("contributors.json 不是有效 UTF-8 JSON") from exc
    if not isinstance(value, dict) or not isinstance(value.get("contributors"), list):
        raise PackageError("contributors.json 缺少 contributors 列表")
    return b'{"contributors": []}\n', ["contributor_identity_records_removed"]


def _sanitize_npmrc(data: bytes) -> tuple[bytes, list[str]]:
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise PackageError(".npmrc 不是有效 UTF-8 文本") from exc
    safe: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")) or "=" not in stripped:
            continue
        key, value = (part.strip() for part in stripped.split("=", 1))
        if key.casefold() in ALLOWED_NPMRC_KEYS and not re.search(r"(?i)https?://[^\s/@:]+:[^\s/@]+@", value):
            safe.append(f"{key}={value}")
    output = ("\n".join(safe) + ("\n" if safe else "")).encode("utf-8")
    return output, ["npmrc_safe_keys_only"]


def _sanitize_doc_note_paths(relative: str, data: bytes) -> tuple[bytes, list[str]]:
    if not relative.startswith("apps/server/src/assets/doc_notes/"):
        return data, []
    try:
        content = data.decode("utf-8")
    except UnicodeError:
        return data, []
    replacements = 0
    replacement = "&lt;local data directory&gt;" if relative.casefold().endswith(".html") else "<local data directory>"
    for pattern in ABSOLUTE_USER_PATH_PATTERNS:
        content, count = pattern.subn(replacement, content)
        replacements += count
    if not replacements:
        return data, []
    return content.encode("utf-8"), ["absolute_user_paths_redacted"]


def _sanitize_source_comment_paths(relative: str, data: bytes) -> tuple[bytes, list[str]]:
    if relative != "packages/commons/src/lib/electron_api_interface.ts":
        return data, []
    try:
        lines = data.decode("utf-8").splitlines(keepends=True)
    except UnicodeError:
        return data, []
    replacements = 0
    for index, line in enumerate(lines):
        if not line.lstrip().startswith(("//", "/*", "#", "*")):
            continue
        for pattern in ABSOLUTE_USER_PATH_PATTERNS:
            lines[index], count = pattern.subn("<local user path>", lines[index])
            replacements += count
    if not replacements:
        return data, []
    return "".join(lines).encode("utf-8"), ["absolute_user_paths_redacted_from_comment"]


def _sanitize_enex_attachment_paths(relative: str, data: bytes) -> tuple[bytes, list[str]]:
    if relative != "packages/trilium-core/src/services/import/samples/File with attachments.enex":
        return data, []
    try:
        content = data.decode("utf-8")
    except UnicodeError:
        return data, []
    replacements = 0
    for pattern in ABSOLUTE_USER_PATH_PATTERNS:
        content, count = pattern.subn("redacted-local-user-path", content)
        replacements += count
    if not replacements:
        return data, []
    return content.encode("utf-8"), ["absolute_user_paths_redacted_from_sample"]


def _sanitize(relative: str, data: bytes) -> tuple[bytes, list[str]]:
    if relative == "contributors.json":
        return _sanitize_contributors(data)
    if relative.endswith("package.json"):
        return _sanitize_package_json(relative, data)
    if relative == ".npmrc":
        return _sanitize_npmrc(data)
    if relative.startswith("apps/server/src/assets/doc_notes/"):
        return _sanitize_doc_note_paths(relative, data)
    if relative == "packages/commons/src/lib/electron_api_interface.ts":
        return _sanitize_source_comment_paths(relative, data)
    if relative == "packages/trilium-core/src/services/import/samples/File with attachments.enex":
        return _sanitize_enex_attachment_paths(relative, data)
    return data, []


def _scan_payload(relative: str, data: bytes) -> None:
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    if "\x00" in content:
        return
    for pattern_index, pattern in enumerate(SECRET_PATTERNS):
        matches = list(pattern.finditer(content))
        if pattern_index == 6:
            matches = [
                match for match in matches
                if not _is_placeholder_auth_comment(content, match)
            ]
        if matches:
            raise PackageError(f"发现疑似凭据内容，拒绝打包: {relative}")
    for pattern in ABSOLUTE_USER_PATH_PATTERNS:
        matches = list(pattern.finditer(content))
        if relative == "apps/server/src/assets/etapi.openapi.yaml":
            # 规范将此路径作为通用数据目录示例；它不是某台机器的路径，因此归档中保留原文。
            matches = [
                match for match in matches
                if match.group(0).strip().replace("\\", "/") != "/home/user/data"
            ]
        if matches:
            raise PackageError(f"发现个人绝对路径，拒绝打包: {relative}")


def _is_placeholder_auth_comment(content: str, match: re.Match[str]) -> bool:
    line_start = content.rfind("\n", 0, match.start()) + 1
    prefix = content[line_start:match.start()].lstrip()
    if not prefix.startswith(("//", "#", "*")):
        return False
    auth = DOCUMENTATION_AUTH_URL.match(match.group(0))
    return bool(
        auth
        and auth.group(1).casefold() in PLACEHOLDER_USER_PARTS
        and auth.group(2).casefold() in PLACEHOLDER_PASSWORD_PARTS
    )


def _canonical_manifest(payload: dict[str, Any]) -> bytes:
    digest_input = dict(payload)
    digest_input.pop("manifest_sha256", None)
    payload["manifest_sha256"] = _sha256(_canonical_json(digest_input))
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _write_reproducible_tar(output_path: Path, entries: dict[str, tuple[Path, int]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as raw_output:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, mtime=0, compresslevel=9) as gz:
                with tarfile.open(fileobj=gz, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                    root = tarfile.TarInfo(f"{PACKAGE_ROOT_NAME}/")
                    root.type = tarfile.DIRTYPE
                    root.mode = 0o755
                    root.uid = root.gid = 0
                    root.uname = root.gname = ""
                    root.mtime = 0
                    archive.addfile(root)
                    for relative in sorted(entries):
                        path, mode = entries[relative]
                        info = tarfile.TarInfo(f"{PACKAGE_ROOT_NAME}/{relative}")
                        info.size = path.stat().st_size
                        info.mode = mode & 0o777
                        info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        info.mtime = 0
                        with path.open("rb") as content:
                            archive.addfile(info, content)
        os.replace(temporary_path, output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def build_source_archive(source: Path, output: Path, overlay_manifest: Path) -> dict[str, Any]:
    source = source.resolve()
    output = output.resolve()
    overlay_manifest = overlay_manifest.resolve()
    if not source.is_dir():
        raise PackageError("--source 必须指向现存的 Git 仓库目录")
    commit = _git_commit(source)
    overlay_files, overlay_paths = _read_overlay_manifest(overlay_manifest, commit)
    overlay_contents: dict[str, bytes] = {}
    mismatches: list[str] = []
    for item in overlay_files:
        relative = item["path"]
        candidate = _safe_target(source, relative)
        if candidate.is_symlink() or not candidate.is_file():
            raise PackageError(f"overlay 文件缺失或不是普通文件: {relative}")
        data = candidate.read_bytes()
        if _sha256(data) != item["sha256"]:
            mismatches.append(relative)
        else:
            overlay_contents[relative] = data
    if mismatches:
        raise PackageError("overlay 哈希与 manifest 不一致: " + ", ".join(mismatches))

    with tempfile.TemporaryDirectory(prefix="readweave-source-") as temporary:
        temporary_root = Path(temporary)
        archive_path = temporary_root / "baseline.tar"
        stage = temporary_root / PACKAGE_ROOT_NAME
        stage.mkdir()
        _archive_head(source, archive_path)

        modes: dict[str, int] = {}
        with tarfile.open(archive_path, mode="r:") as archive:
            for member in archive:
                if member.isdir():
                    continue
                relative = _safe_repo_path(member.name)
                if not _should_include(relative, overlay_paths):
                    continue
                if not member.isfile():
                    raise PackageError(f"允许打包的 Git 基线路径不是普通文件: {relative}")
                data = _read_tar_member(archive, member)
                target = _safe_target(stage, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                modes[relative] = member.mode & 0o777 or 0o644

        for item in overlay_files:
            relative = item["path"]
            data = overlay_contents[relative]
            target = _safe_target(stage, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            modes.setdefault(relative, 0o644)

        for required in ("LICENSE", "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml"):
            if not (stage / required).is_file():
                raise PackageError(f"Git 基线缺少源码包必需文件: {required}")

        transformations: list[dict[str, Any]] = []
        for relative in sorted(modes):
            if (
                relative == ".npmrc"
                or relative == "contributors.json"
                or relative == "package.json"
                or relative.endswith("/package.json")
                or relative.startswith("apps/server/src/assets/doc_notes/")
                or relative == "packages/commons/src/lib/electron_api_interface.ts"
                or relative == "packages/trilium-core/src/services/import/samples/File with attachments.enex"
            ):
                target = _safe_target(stage, relative)
                sanitized, actions = _sanitize(relative, target.read_bytes())
                target.write_bytes(sanitized)
                if actions:
                    transformations.append({"path": relative, "actions": actions})

        payload_entries: dict[str, tuple[Path, int]] = {}
        file_records: list[dict[str, Any]] = []
        for relative in sorted(modes):
            path = _safe_target(stage, relative)
            data = path.read_bytes()
            _scan_payload(relative, data)
            payload_entries[relative] = (path, modes[relative])
            file_records.append({"path": relative, "size": len(data), "sha256": _sha256(data)})

        included_overlay = [
            {"path": item["path"], "sha256": item["sha256"], "test": item["test"]}
            for item in sorted(overlay_files, key=lambda entry: entry["path"])
        ]
        manifest = {
            "schema_version": 1,
            "package_root": PACKAGE_ROOT_NAME,
            "source_commit": commit,
            "baseline_ref": commit[:10],
            "license": "AGPL-3.0-only",
            "license_and_notice_files": [
                path for path in sorted(modes)
                if re.search(r"(?:license|licence|notice)", PurePosixPath(path).name, re.IGNORECASE)
            ],
            "build_support_files": sorted(BUILD_SUPPORT_FILES),
            "runtime_support_files": sorted(RUNTIME_SUPPORT_FILES),
            "overlay": included_overlay,
            "included_file_count": len(file_records),
            "included_roots": sorted(SOURCE_ROOTS),
            "build_commands": {
                "install": "corepack pnpm install --frozen-lockfile --ignore-scripts",
                "client": "corepack pnpm client:build",
                "server": "corepack pnpm server:build",
                "native_panel": "node integrations/readweave/build_native.mjs <source-directory>",
            },
            "transformations": transformations,
            "files": file_records,
        }
        manifest_bytes = _canonical_manifest(manifest)
        manifest_path = stage / "SOURCE-MANIFEST.json"
        manifest_path.write_bytes(manifest_bytes)
        payload_entries["SOURCE-MANIFEST.json"] = (manifest_path, 0o644)
        _write_reproducible_tar(output, payload_entries)

    archive_hash = _sha256_file(output)
    sidecar = output.with_name(output.name + ".sha256")
    sidecar.write_text(f"{archive_hash}  {output.name}\n", encoding="ascii", newline="\n")
    result = dict(manifest)
    result["archive_sha256"] = archive_hash
    result["output_name"] = output.name
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="从指定 Git 仓库的 HEAD 和精确 overlay 清单生成可复现的 ReadWeave 源码包。"
    )
    parser.add_argument("--source", required=True, type=Path, help="ReadWeave Git 仓库路径")
    parser.add_argument("--output", required=True, type=Path, help="源码包 .tar.gz 的输出路径")
    parser.add_argument(
        "--overlay-manifest",
        type=Path,
        default=DEFAULT_OVERLAY_MANIFEST,
        help="精确列出本次覆盖文件及哈希的 JSON 清单",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = build_source_archive(args.source, args.output, args.overlay_manifest)
    except PackageError as exc:
        print(f"package_source: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "output": result["output_name"],
        "source_commit": result["source_commit"],
        "included_file_count": result["included_file_count"],
        "manifest_sha256": result["manifest_sha256"],
        "archive_sha256": result["archive_sha256"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
