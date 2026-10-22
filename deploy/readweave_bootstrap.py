"""从公开源码快照部署独立的 ReadWeave，并按需接入 LessonWeave"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


BRIDGE_KEY = "LESSONWEAVE_READWEAVE_BRIDGE"
READWEAVE_URL_KEY = "LESSONWEAVE_READWEAVE_URL"
READWEAVE_TOKEN_KEY = "LESSONWEAVE_READWEAVE_TOKEN"
TRILIUM_URL_KEY = "LESSONWEAVE_TRILIUM_URL"
TRILIUM_TOKEN_KEY = "LESSONWEAVE_TRILIUM_TOKEN"
TRILIUM_ROOT_KEY = "LESSONWEAVE_TRILIUM_ROOT"
TRILIUM_TRASH_KEY = "LESSONWEAVE_TRILIUM_TRASH"
CONTAINER_NAME = "lessonweave-readweave"
VOLUME_NAME = "lessonweave-readweave-data"
VOLUME_LABEL = "lessonweave.readweave=1"
CONTAINER_LABEL = "lessonweave.readweave=1"
IMAGE_BUILD_REVISION = "2"
CONTAINER_DATA_DIR = "/home/node/trilium-data"
CONTAINER_PORT = 8080
SOURCE_ROOT_NAME = "readweave-source"
REQUIRED_FILES = (
    "LICENSE",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "apps/server/start-docker.sh",
    "apps/server/docker/package.json",
    "apps/server/docker/pnpm-workspace.yaml",
    "apps/server/src/main.ts",
)


def parse_env_file(path: Path) -> tuple[dict[str, str], list[str]]:
    if not path.is_file():
        return {}, []
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        if item.startswith("export "):
            item = item[7:].lstrip()
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values, lines


def effective_config(env_path: Path) -> dict[str, str]:
    file_values, _ = parse_env_file(env_path)
    keys = (BRIDGE_KEY, READWEAVE_URL_KEY, READWEAVE_TOKEN_KEY, TRILIUM_URL_KEY, TRILIUM_TOKEN_KEY, TRILIUM_ROOT_KEY, TRILIUM_TRASH_KEY)
    for key in keys:
        shell_value = os.environ.get(key, "").strip()
        file_value = file_values.get(key, "").strip()
        if shell_value and file_value and shell_value != file_value:
            raise SystemExit(f"当前 shell 与 {env_path} 中的 {key} 不一致；部署器不会静默替换现有配置")
    return {key: os.environ.get(key, file_values.get(key, "")).strip() for key in keys}


def verify_source_manifest(archive: tarfile.TarFile, members: list[tarfile.TarInfo]) -> dict:
    manifest_member = next((member for member in members if member.name == f"{SOURCE_ROOT_NAME}/SOURCE-MANIFEST.json"), None)
    if manifest_member is None or not manifest_member.isfile():
        raise SystemExit("ReadWeave 源码归档缺少 SOURCE-MANIFEST.json，无法核对文件清单")
    stream = archive.extractfile(manifest_member)
    if stream is None:
        raise SystemExit("无法读取 ReadWeave 源码归档中的 SOURCE-MANIFEST.json")
    try:
        with stream:
            manifest = json.loads(stream.read())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit("ReadWeave 源码归档中的 SOURCE-MANIFEST.json 无法解析") from error
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("package_root") != SOURCE_ROOT_NAME or manifest.get("license") != "AGPL-3.0-only":
        raise SystemExit("ReadWeave 源码清单的格式、根目录或许可证标记不符合要求")
    entries = manifest.get("files")
    if not isinstance(entries, list) or manifest.get("included_file_count") != len(entries):
        raise SystemExit("ReadWeave 源码清单中的文件数量不正确")
    supplied_digest = manifest.get("manifest_sha256")
    digest_input = dict(manifest)
    digest_input.pop("manifest_sha256", None)
    expected_digest = hashlib.sha256(json.dumps(digest_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if supplied_digest != expected_digest:
        raise SystemExit("ReadWeave 源码清单的完整性校验失败")

    file_members = [member for member in members if member.isfile()]
    file_map: dict[str, tarfile.TarInfo] = {}
    for member in file_members:
        relative = str(PurePosixPath(member.name).relative_to(SOURCE_ROOT_NAME))
        if relative in file_map:
            raise SystemExit("ReadWeave 源码归档重复包含同一路径")
        file_map[relative] = member
    if "SOURCE-MANIFEST.json" not in file_map:
        raise SystemExit("ReadWeave 源码归档中的文件根目录不正确")

    records: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit("ReadWeave 源码清单中的文件记录格式不正确")
        relative, expected_hash, size = entry.get("path"), entry.get("sha256"), entry.get("size")
        if (not isinstance(relative, str) or not relative or "\\" in relative
                or PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts
                or PurePosixPath(relative).as_posix() != relative
                or not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
                or not isinstance(size, int) or isinstance(size, bool) or size < 0 or relative in records):
            raise SystemExit("ReadWeave 源码清单中包含重复或无效的文件记录")
        records[relative] = entry
    if set(file_map) != set(records) | {"SOURCE-MANIFEST.json"}:
        raise SystemExit("ReadWeave 源码归档与清单所列文件不一致")
    for relative, entry in records.items():
        member = file_map[relative]
        if member.size != entry["size"]:
            raise SystemExit(f"ReadWeave 源码文件大小与清单不一致：{relative}")
        source = archive.extractfile(member)
        if source is None:
            raise SystemExit(f"无法读取 ReadWeave 源码文件：{relative}")
        digest = hashlib.sha256()
        with source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != entry["sha256"]:
            raise SystemExit(f"ReadWeave 源码文件哈希与清单不一致：{relative}")
    return manifest


def apply_source_patch(source_root: Path, patch_path: Path) -> None:
    """保留已发布的源码包，在构建前应用本仓库随附的读取修复"""
    try:
        result = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(patch_path.resolve())],
            cwd=source_root, capture_output=True, text=True,
        )
    except FileNotFoundError as error:
        raise SystemExit("请先安装 Git，部署器需要它应用仓库随附的 ReadWeave 源码修复") from error
    if result.returncode:
        raise SystemExit("ReadWeave 源码与仓库随附的读取修复不匹配，尚未构建或更改笔记库\n" + result.stderr.strip())


def selected_pair(config: dict[str, str]) -> tuple[str, str]:
    readweave_url = config.get(READWEAVE_URL_KEY, "")
    trilium_url = config.get(TRILIUM_URL_KEY, "")
    readweave_token = config.get(READWEAVE_TOKEN_KEY, "")
    trilium_token = config.get(TRILIUM_TOKEN_KEY, "")
    if readweave_url and trilium_url and normalize_url(readweave_url) != normalize_url(trilium_url):
        raise SystemExit("ReadWeave 与 Trilium 的网址指向不同实例；部署器不会替你改换现有笔记库")
    if readweave_token and trilium_token and readweave_token != trilium_token:
        raise SystemExit("ReadWeave 与 Trilium 的令牌不一致；部署器不会替你改换现有凭据")
    if (readweave_token and not readweave_url) or (trilium_token and not trilium_url):
        raise SystemExit("ReadWeave 或 Trilium 令牌缺少同名网址；部署器不会把两组配置交叉拼接")
    if readweave_url and not readweave_token and trilium_token or trilium_url and not trilium_token and readweave_token:
        raise SystemExit("ReadWeave 与 Trilium 配置只有一组完整；请先核对网址和令牌是否属于同一实例")
    return readweave_url or trilium_url, readweave_token or trilium_token


def normalize_url(value: str) -> str:
    url = value.strip().rstrip("/")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
        raise SystemExit("ReadWeave 网址必须是 http 或 https 地址，且不能在网址中放入账号或令牌")
    if parts.query or parts.fragment:
        raise SystemExit("ReadWeave 网址不能带查询参数或片段")
    return url


def validate_archive(path: Path, manifest_path: Path, extract_to: Path | None = None) -> tuple[str, Path | None]:
    if not path.is_file():
        raise SystemExit(f"找不到 ReadWeave 源码归档：{path}")
    digest = hashlib.sha256()
    with path.open("rb") as archive_file:
        for block in iter(lambda: archive_file.read(1024 * 1024), b""):
            digest.update(block)
    archive_hash = digest.hexdigest()
    try:
        with tarfile.open(path, "r:*") as archive:
            members = archive.getmembers()
            if not members:
                raise SystemExit("ReadWeave 源码归档没有文件")
            for member in members:
                rel = PurePosixPath(member.name)
                if "\\" in member.name or rel.is_absolute() or ".." in rel.parts or not rel.parts or rel.parts[0] != SOURCE_ROOT_NAME:
                    raise SystemExit("ReadWeave 源码归档路径无效；归档内所有文件都应位于 readweave-source/ 下")
                expected_name = rel.as_posix()
                valid_names = {expected_name, expected_name + "/"} if member.isdir() else {expected_name}
                if member.name not in valid_names:
                    raise SystemExit("ReadWeave 源码归档包含非规范路径")
                if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise SystemExit("ReadWeave 源码归档包含不支持的链接或特殊文件")
            source_manifest = verify_source_manifest(archive, members)
            file_names = {str(PurePosixPath(m.name).relative_to(SOURCE_ROOT_NAME)) for m in members if m.isfile()}
            missing = [name for name in REQUIRED_FILES if name not in file_names]
            if missing:
                raise SystemExit("ReadWeave 源码归档缺少构建所需文件：" + ", ".join(missing))
            source_root = None
            if extract_to is not None:
                source_root = extract_to / SOURCE_ROOT_NAME
                source_root.mkdir(parents=True, exist_ok=False)
                for member in members:
                    rel_parts = PurePosixPath(member.name).parts[1:]
                    target = source_root.joinpath(*rel_parts)
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = archive.extractfile(member)
                    if source is None:
                        raise SystemExit("无法读取 ReadWeave 源码归档中的文件")
                    with source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
    except (tarfile.TarError, OSError) as error:
        raise SystemExit(f"ReadWeave 源码归档无法读取：{error}") from error
    verify_manifest(source_root, manifest_path, source_manifest) if source_root is not None else None
    return archive_hash, source_root


def verify_manifest(source_root: Path | None, manifest_path: Path, source_manifest: dict) -> None:
    if source_root is None:
        return
    if not manifest_path.is_file():
        raise SystemExit("仓库中找不到 integrations/readweave/backend-source-manifest.json，无法核对公开源码快照")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"ReadWeave 源码核对清单无法读取：{error}") from error
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise SystemExit("ReadWeave 源码核对清单没有文件记录")
    if any(not isinstance(entry, dict) or not isinstance(entry.get("path"), str)
           or not isinstance(entry.get("sha256"), str)
           or ("test" in entry and not isinstance(entry.get("test"), bool)) for entry in entries):
        raise SystemExit("ReadWeave 源码核对清单格式不正确")
    packaged_overlay = source_manifest.get("overlay")
    if not isinstance(packaged_overlay, list) or any(not isinstance(entry, dict)
            or not isinstance(entry.get("path"), str) or not isinstance(entry.get("sha256"), str)
            or ("test" in entry and not isinstance(entry.get("test"), bool)) for entry in packaged_overlay):
        raise SystemExit("ReadWeave 源码清单中的桥接文件记录格式不正确")
    expected_overlay = sorted((entry.get("path"), entry.get("sha256"), bool(entry.get("test", False))) for entry in entries if isinstance(entry, dict))
    actual_overlay = sorted((entry.get("path"), entry.get("sha256"), bool(entry.get("test", False))) for entry in packaged_overlay)
    if not expected_overlay or expected_overlay != actual_overlay:
        raise SystemExit("源码包采用的桥接文件清单与当前 LessonWeave 不一致")
    for entry in entries:
        relative = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise SystemExit("ReadWeave 源码核对清单格式不正确")
        relative_path = PurePosixPath(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts or "\\" in relative:
            raise SystemExit("ReadWeave 源码核对清单包含无效路径")
        candidate = source_root.joinpath(*relative_path.parts)
        if not candidate.is_file():
            raise SystemExit(f"源码快照缺少桥接清单文件：{relative}")
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if digest.lower() != expected.lower():
            raise SystemExit(f"源码快照与桥接核对清单不一致：{relative}")


def write_env_file(path: Path, updates: dict[str, str]) -> None:
    if any("\n" in value or "\r" in value for value in updates.values()):
        raise SystemExit("环境变量值不能包含换行")
    existing, lines = parse_env_file(path)
    replacements = dict(updates)
    output: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        candidate = stripped[7:].lstrip() if stripped.startswith("export ") else stripped
        key = candidate.split("=", 1)[0].strip() if "=" in candidate else ""
        if key in replacements:
            if key not in seen:
                output.append(f"{key}={replacements[key]}")
                seen.add(key)
            continue
        output.append(line)
    for key, value in replacements.items():
        if key not in seen:
            output.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write("\n".join(output) + "\n")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def updates_for_pending_setup(url: str) -> dict[str, str]:
    return {
        BRIDGE_KEY: "0",
        READWEAVE_URL_KEY: url,
        TRILIUM_URL_KEY: url,
    }


def updates_for_connected_setup(url: str, token: str, root_id: str, trash_id: str) -> dict[str, str]:
    return {
        BRIDGE_KEY: "1",
        READWEAVE_URL_KEY: url,
        READWEAVE_TOKEN_KEY: token,
        TRILIUM_URL_KEY: url,
        TRILIUM_TOKEN_KEY: token,
        TRILIUM_ROOT_KEY: root_id,
        TRILIUM_TRASH_KEY: trash_id,
    }


def etapi_call(base_url: str, token: str, method: str, path: str, payload: dict | None = None) -> dict | None:
    url = normalize_url(base_url) + "/etapi/" + path.lstrip("/")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Authorization": token}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except HTTPError as error:
        if method == "GET" and error.code == 404:
            return None
        if method == "POST" and error.code == 409:
            return None
        raise SystemExit(f"ReadWeave ETAPI 请求未完成（HTTP {error.code}）；请核对服务权限和配置") from error
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise SystemExit("ReadWeave ETAPI 无法完成请求；请核对网址、令牌和服务状态") from error


def check_bridge_capabilities(base_url: str, token: str) -> dict:
    url = normalize_url(base_url) + "/api/lessonweave/capabilities"
    request = Request(url, headers={"Authorization": token, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            value = json.loads(response.read())
    except HTTPError as error:
        if error.code in {401, 403}:
            raise SystemExit("ReadWeave 没有接受 ETAPI token；部署器不会启用桥接或改写凭据") from error
        raise SystemExit(f"ReadWeave 桥接能力检查未完成（HTTP {error.code}）；请先部署匹配的 LessonWeave 桥接") from error
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise SystemExit("ReadWeave 桥接能力接口无法读取；请核对服务版本、网址和服务状态") from error
    if not isinstance(value, dict) or value.get("version") != "1" or value.get("schemaVersion") != "1.2":
        raise SystemExit("ReadWeave 桥接版本与当前 LessonWeave 不匹配；桥接保持关闭，现有笔记库未被修改")
    return value


def stable_note_id(key: str) -> str:
    return "lw" + hashlib.sha256(("lessonweave.bootstrap:" + key).encode("utf-8")).hexdigest()[:24]


def ensure_note(base_url: str, token: str, note_id: str, parent_id: str | None, title: str) -> str:
    existing = etapi_call(base_url, token, "GET", "notes/" + quote(note_id, safe=""))
    if existing is not None:
        if existing.get("noteId") != note_id:
            raise SystemExit("ReadWeave 返回的笔记身份与请求不一致；保留现有数据并停止配置")
        if parent_id and parent_id not in existing.get("parentNoteIds", []):
            raise SystemExit("稳定 ID 已被其他笔记占用；部署器不会移动或覆盖该笔记")
        return note_id
    payload = {"noteId": note_id, "parentNoteId": parent_id or "root", "title": title, "type": "book", "content": ""}
    created = etapi_call(base_url, token, "POST", "create-note", payload)
    if created is None:
        existing = etapi_call(base_url, token, "GET", "notes/" + quote(note_id, safe=""))
        if existing is None or existing.get("noteId") != note_id or parent_id and parent_id not in existing.get("parentNoteIds", []):
            raise SystemExit("ReadWeave 创建固定目录时遇到冲突；保留现有内容并停止配置")
    elif (created.get("note") or {}).get("noteId") != note_id:
        raise SystemExit("ReadWeave 没有按请求创建固定目录；部署器不会继续写配置")
    return note_id


def ensure_native_library(base_url: str, token: str, config: dict[str, str]) -> tuple[str, str]:
    root_id = config.get(TRILIUM_ROOT_KEY, "") or stable_note_id("root")
    trash_id = config.get(TRILIUM_TRASH_KEY, "") or stable_note_id("trash")
    if root_id == trash_id:
        raise SystemExit("LessonWeave 根目录和回收站不能使用同一个笔记 ID")
    if config.get(TRILIUM_ROOT_KEY):
        root_note = etapi_call(base_url, token, "GET", "notes/" + quote(root_id, safe=""))
        if root_note is None or root_note.get("noteId") != root_id:
            raise SystemExit("私有环境文件中的 LessonWeave 根目录无法在当前 ReadWeave 实例读取")
    else:
        ensure_note(base_url, token, root_id, "root", "LessonWeave")
    if config.get(TRILIUM_TRASH_KEY):
        trash_note = etapi_call(base_url, token, "GET", "notes/" + quote(trash_id, safe=""))
        if trash_note is None or trash_note.get("noteId") != trash_id:
            raise SystemExit("私有环境文件中的 LessonWeave 回收站无法在当前 ReadWeave 实例读取")
        if root_id not in trash_note.get("parentNoteIds", []):
            raise SystemExit("私有环境文件中的 LessonWeave 回收站不在已配置的根目录下；部署器不会移动或替换该笔记")
    else:
        ensure_note(base_url, token, trash_id, root_id, "LessonWeave 回收站")
    return root_id, trash_id


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, text=True, capture_output=capture)
    except FileNotFoundError as error:
        raise SystemExit(f"找不到命令 {command[0]}；请先安装并启动 Docker") from error
    except subprocess.CalledProcessError as error:
        if capture and error.stdout:
            print(error.stdout, end="")
        if capture and error.stderr:
            print(error.stderr, end="", file=sys.stderr)
        raise SystemExit(f"命令执行失败：{command[0]}；保留现有数据卷后再检查 Docker 状态") from error


def docker_inspect(kind: str, name: str) -> dict | None:
    result = subprocess.run(["docker", kind, "inspect", name], text=True, capture_output=True)
    if result.returncode:
        return None
    try:
        value = json.loads(result.stdout)
        return value[0]
    except (json.JSONDecodeError, IndexError, TypeError):
        raise SystemExit(f"Docker 无法读取 {kind} {name} 的状态")


def health_check(base_url: str, timeout_seconds: int = 120) -> None:
    health_url = normalize_url(base_url) + "/api/health-check"
    deadline = time.monotonic() + timeout_seconds
    last_status = "尚未响应"
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=3) as response:
                if 200 <= response.status < 300:
                    return
                last_status = f"HTTP {response.status}"
        except HTTPError as error:
            if 200 <= error.code < 300:
                return
            last_status = f"HTTP {error.code}"
        except (URLError, TimeoutError, OSError) as error:
            last_status = type(error).__name__
        time.sleep(2)
    raise SystemExit(f"ReadWeave 尚未通过 /api/health-check（最近状态：{last_status}）；容器和数据卷已保留")


def managed_container_url() -> str | None:
    container = docker_inspect("container", CONTAINER_NAME)
    if container is None:
        return None
    labels = (container.get("Config") or {}).get("Labels") or {}
    if labels.get("lessonweave.readweave") != "1":
        raise SystemExit(f"Docker 容器名 {CONTAINER_NAME} 已被其他容器占用；部署器不会删除或改写它")
    bindings = (container.get("HostConfig") or {}).get("PortBindings") or {}
    candidates = bindings.get(f"{CONTAINER_PORT}/tcp") or []
    binding = next((row for row in candidates if row.get("HostIp") in {"127.0.0.1", "::1"}), None)
    if binding is None or len(candidates) != 1:
        raise SystemExit("现有 ReadWeave 容器没有只绑定本机回环地址；部署器不会扩大它的网络暴露")
    port = binding.get("HostPort")
    if not port or not port.isdigit():
        raise SystemExit("现有 ReadWeave 容器没有可用的本机端口")
    state = container.get("State") or {}
    if not state.get("Running"):
        run(["docker", "start", CONTAINER_NAME])
    host = "[::1]" if binding.get("HostIp") == "::1" else "127.0.0.1"
    return f"http://{host}:{port}"


def ensure_named_volume() -> None:
    volume = docker_inspect("volume", VOLUME_NAME)
    if volume is not None:
        labels = volume.get("Labels") or {}
        if labels.get("lessonweave.readweave") != "1":
            raise SystemExit(f"Docker 数据卷名 {VOLUME_NAME} 已存在且没有本部署器标记；部署器不会使用或覆盖它")
        return
    run(["docker", "volume", "create", "--label", VOLUME_LABEL, VOLUME_NAME], capture=True)


def build_and_start(source_root: Path, source_hash: str, port: int) -> str:
    docker_info = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], text=True, capture_output=True)
    if docker_info.returncode:
        raise SystemExit("Docker 服务尚未运行；启动 Docker 后重新执行，部署器不会创建系统登录或模型凭据")
    existing_url = managed_container_url()
    if existing_url:
        health_check(existing_url)
        return existing_url
    ensure_named_volume()
    image_tag = f"lessonweave-readweave:{source_hash[:12]}-r{IMAGE_BUILD_REVISION}"
    dockerfile = source_root / ".lessonweave-readweave.Dockerfile"
    dockerfile.write_text(
        """FROM node:24.18.0-bookworm-slim AS source-builder
RUN corepack enable && apt-get update && apt-get install -y --no-install-recommends python3 make g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /source
COPY . .
RUN corepack pnpm install --frozen-lockfile --ignore-scripts
RUN corepack pnpm server:build

FROM node:24.18.0-bookworm-slim AS runtime-dependencies
RUN corepack enable && apt-get update && apt-get install -y --no-install-recommends python3 make g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /usr/src/app/build
COPY apps/server/docker/package.json ./package.json
COPY apps/server/docker/pnpm-workspace.yaml ./pnpm-workspace.yaml
RUN pnpm install --no-frozen-lockfile --prod && pnpm rebuild

FROM node:24.18.0-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/* /var/cache/apt/*
WORKDIR /usr/src/app
COPY --from=source-builder /source/apps/server/dist/ /usr/src/app/
COPY --from=source-builder /source/apps/server/start-docker.sh /usr/src/app/
RUN rm -rf /usr/src/app/node_modules/better-sqlite3
COPY --from=runtime-dependencies /usr/src/app/build/node_modules/better-sqlite3 /usr/src/app/node_modules/better-sqlite3
ENV TRILIUM_DATA_DIR=/home/node/trilium-data TRILIUM_PORT=8080 TRILIUM_ENV=production
EXPOSE 8080
CMD [\"sh\", \"./start-docker.sh\"]
HEALTHCHECK --start-period=10s CMD exec gosu node node /usr/src/app/docker_healthcheck.cjs
""",
        encoding="utf-8",
    )
    run(["docker", "build", "--tag", image_tag, "--file", str(dockerfile), str(source_root)], capture=False)
    run(
        [
            "docker", "run", "--detach", "--name", CONTAINER_NAME,
            "--restart", "unless-stopped",
            "--label", CONTAINER_LABEL,
            "--publish", f"127.0.0.1:{port}:{CONTAINER_PORT}",
            "--mount", f"type=volume,src={VOLUME_NAME},dst={CONTAINER_DATA_DIR}",
            "--env", f"TRILIUM_DATA_DIR={CONTAINER_DATA_DIR}",
            "--env", f"TRILIUM_PORT={CONTAINER_PORT}",
            "--env", "TRILIUM_ENV=production",
            image_tag,
        ],
        capture=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    health_check(base_url)
    return base_url


def get_token(config: dict[str, str], dry_run: bool) -> str:
    token = config.get(READWEAVE_TOKEN_KEY) or config.get(TRILIUM_TOKEN_KEY) or ""
    if token:
        return token
    if dry_run:
        return ""
    if not sys.stdin.isatty():
        raise SystemExit("尚未配置 ReadWeave ETAPI 令牌；完成原生首次设置后，交互运行 --configure-token 输入令牌")
    token = getpass.getpass("ReadWeave ETAPI token（输入内容不会显示）：").strip()
    if not token or re.search(r"\s", token):
        raise SystemExit("ReadWeave ETAPI 令牌不能为空或包含空白字符")
    return token


def configure_existing(args: argparse.Namespace, root: Path, env_path: Path, config: dict[str, str]) -> int:
    pair_config = dict(config)
    if args.url:
        if pair_config.get(READWEAVE_TOKEN_KEY) and not pair_config.get(READWEAVE_URL_KEY):
            pair_config[READWEAVE_URL_KEY] = args.url
        if pair_config.get(TRILIUM_TOKEN_KEY) and not pair_config.get(TRILIUM_URL_KEY):
            pair_config[TRILIUM_URL_KEY] = args.url
    old_url, old_token = selected_pair(pair_config)
    url = normalize_url(args.url or old_url or f"http://127.0.0.1:{args.port}")
    if old_url and normalize_url(old_url) != url:
        raise SystemExit("新旧 ReadWeave 网址不同；为避免改写已有笔记库，请先检查环境配置")
    token = get_token(config, args.dry_run)
    if args.dry_run:
        state = "已有令牌" if old_token else "需要首次通过隐藏输入读取 ETAPI 令牌"
        print(f"dry-run：将检查 {url}，{state}，幂等确认 LessonWeave 根目录和回收站，并同步两组环境变量；不会写入配置或创建笔记")
        return 0
    health_check(url)
    if not token:
        token = get_token(config, False)
    if old_token and old_token != token:
        raise SystemExit("当前 ReadWeave 与 Trilium 令牌不一致；部署器不会替换现有凭据")
    check_bridge_capabilities(url, token)
    root_id, trash_id = ensure_native_library(url, token, config)
    write_env_file(env_path, updates_for_connected_setup(url, token, root_id, trash_id))
    print(f"ReadWeave 已通过 /api/health-check；LessonWeave 根目录和回收站已确认，配置已保存到 {env_path}；请重启 LessonWeave 服务")
    return 0


def deploy_new(args: argparse.Namespace, root: Path, env_path: Path, config: dict[str, str]) -> int:
    url, token = selected_pair(config)
    if url and not token:
        raise SystemExit("已发现 ReadWeave 网址但没有成对令牌；为避免另建笔记库，请先完成 --configure-token")
    if token and not url:
        raise SystemExit("已发现 ReadWeave 令牌但没有网址；请用 --configure-token --url 指定同一实例")
    if url and token:
        if args.dry_run:
            print(f"dry-run：复用已配置的 ReadWeave 实例 {normalize_url(url)}；将检查根目录和回收站，不会创建容器或改写配置")
            return 0
        health_check(url)
        check_bridge_capabilities(normalize_url(url), token)
        root_id, trash_id = ensure_native_library(normalize_url(url), token, config)
        write_env_file(env_path, updates_for_connected_setup(normalize_url(url), token, root_id, trash_id))
        print(f"已复用现有 ReadWeave 实例 {normalize_url(url)}；没有启动重复容器，根目录和回收站已确认，配置已同步到 {env_path}")
        return 0

    source_value = args.source
    if not source_value:
        if args.dry_run:
            print("dry-run：没有现成的 ReadWeave 网址和令牌；要新建独立库，请提供 --source 源码归档")
            return 0
        if not shutil.which("docker"):
            raise SystemExit("找不到 Docker 命令；已有实例请提供完整网址和令牌，新建独立库请先安装并启动 Docker")
        existing_url = managed_container_url()
        if existing_url:
            health_check(existing_url)
            write_env_file(env_path, updates_for_pending_setup(existing_url))
            print(f"已复用本机 ReadWeave 容器 {existing_url}；请完成原生首次设置，再运行 --configure-token")
            return 0
        raise SystemExit("没有现成的 ReadWeave 配置；新建独立库时请用 --source 指定公开源码归档")

    source_path = Path(source_value).expanduser().resolve()
    manifest_path = root / "integrations" / "readweave" / "backend-source-manifest.json"
    patch_path = root / "integrations" / "readweave" / "patches" / "scoped-export.patch"
    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="lessonweave-readweave-check-") as temporary:
            source_hash, source_root = validate_archive(source_path, manifest_path, Path(temporary))
            assert source_root is not None
            apply_source_patch(source_root, patch_path)
        print(f"dry-run：将从公开源码快照构建独立 ReadWeave 镜像（归档 SHA-256 {source_hash[:12]}），绑定 127.0.0.1:{args.port}，使用独立 Docker 数据卷；不会运行 Docker 或改写配置")
        return 0
    if not shutil.which("docker"):
        raise SystemExit("找不到 Docker 命令；请先安装 Docker 并启动 Docker 服务")
    with tempfile.TemporaryDirectory(prefix="lessonweave-readweave-") as temporary:
        source_hash, source_root = validate_archive(source_path, manifest_path, Path(temporary))
        assert source_root is not None
        apply_source_patch(source_root, patch_path)
        base_url = build_and_start(source_root, source_hash, args.port)
    write_env_file(env_path, updates_for_pending_setup(base_url))
    print(f"独立 ReadWeave 已通过 /api/health-check，且只监听 {base_url}")
    print(f"原生数据保存在 Docker 数据卷 {VOLUME_NAME}；首次登录和令牌仍需由你在浏览器中创建")
    print(f"本机配置已写入 {env_path}，ReadWeave 桥接保持关闭；完成首次设置后运行 deploy/readweave_bootstrap.py --configure-token")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="部署独立 ReadWeave，或把现有实例接入 LessonWeave")
    parser.add_argument("--source", help="公开 ReadWeave 源码 .tar.gz；新建独立库时必填")
    parser.add_argument("--port", type=int, default=18961, help="本机回环端口（默认 18961）")
    parser.add_argument("--url", help="现有 ReadWeave 实例的网址；仅用于 --configure-token")
    parser.add_argument("--env-file", help="LessonWeave 环境文件；默认使用仓库根目录的 .env")
    parser.add_argument("--configure-token", "--configure", dest="configure", action="store_true", help="验证实例、隐藏读取令牌，并确认根目录与回收站")
    parser.add_argument("--dry-run", action="store_true", help="只显示将执行的部署步骤，不写配置、不运行 Docker")
    args = parser.parse_args()
    if args.port < 1024 or args.port > 65535:
        parser.error("--port 必须在 1024 到 65535 之间")
    if args.url and not args.configure:
        parser.error("--url 只能与 --configure-token 一起使用")
    root = Path(__file__).resolve().parents[1]
    env_path = Path(args.env_file).expanduser().resolve() if args.env_file else root / ".env"
    config = effective_config(env_path)
    if args.configure:
        return configure_existing(args, root, env_path, config)
    return deploy_new(args, root, env_path, config)


if __name__ == "__main__":
    raise SystemExit(main())
