from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "integrations" / "readweave"))
import package_source  # noqa: E402


class ReadWeavePackageSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self._write("LICENSE", "AGPL-3.0-only\n")
        self._write("NOTICE", "Third-party notices are retained.\n")
        self._write("contributors.json", json.dumps({
            "contributors": [{"name": "Private Example", "url": "https://example.invalid/account"}],
            "warning": "generated metadata",
        }))
        self._write("package.json", json.dumps({
            "name": "@example/source",
            "author": {"name": "Public Team", "email": "public@example.invalid"},
            "scripts": {
                "client:build": "pnpm run --filter client build",
                "server:build": "pnpm run --filter server build",
                "readweave:privacy": "node scripts/readweave/privacy-scan.mjs",
                "postinstall": "pnpm prepare",
            },
        }))
        self._write("pnpm-lock.yaml", "lockfileVersion: '9.0'\n")
        self._write("pnpm-workspace.yaml", "packages:\n  - apps/*\n  - packages/*\n")
        self._write(".npmrc", "save-prefix=^\n//private.invalid/:_authToken=not-a-token\n")
        self._write(".pnpmfile.cjs", "module.exports = { hooks: {} };\n")
        for path in (
            "apps/client/package.json",
            "apps/server/package.json",
            "apps/desktop/package.json",
            "packages/commons/package.json",
            "packages/ckeditor5/package.json",
            "packages/trilium-e2e/package.json",
        ):
            self._write(path, json.dumps({"name": path, "scripts": {"build": "echo build"}}))
        self._write("apps/server/docker/package.json", json.dumps({"dependencies": {"better-sqlite3": "12.0.0"}}))
        self._write("apps/server/docker/pnpm-workspace.yaml", "allowBuilds:\n  better-sqlite3: true\n")
        self._write("apps/server/docker/traefik/compose.yml", "services: {}\n")
        self._write("apps/client/src/client.ts", "export const client = true;\n")
        self._write("apps/server/src/server.ts", "export const server = true;\n")
        self._write("apps/server/src/assets/THIRD-PARTY-NOTICES.md", "Third-party notice.\n")
        for path in package_source.RUNTIME_SUPPORT_FILES:
            if path.endswith(".md"):
                self._write(path, "Runtime asset.\n")
        self._write("apps/server/src/assets/other/internal-notes.md", "Not a runtime asset.\n")
        self._write("apps/desktop/src/private.ts", "export const desktop = true;\n")
        self._write("packages/commons/src/index.ts", "export const common = true;\n")
        self._write("packages/trilium-core/src/test/becca_easy_mocking.ts", "export const easyMock = true;\n")
        self._write("packages/trilium-core/src/test/becca_mocking.ts", "export const mock = true;\n")
        self._write("packages/trilium-e2e/src/private.ts", "export const e2e = true;\n")
        self._write(".private/secrets.json", "{}\n")
        self._write("apps/client/.env.local", "SECRET=ignored\n")
        self._write("apps/client/node_modules/pkg/index.js", "ignored\n")
        self._write("evals/case.json", "{}\n")
        self._write("docs/private.md", "ignored\n")
        self.overlay_path = "apps/server/src/routes/api/readweave.spec.ts"
        self.overlay_data = b"export const bridgeTest = true;\n"
        self._write(self.overlay_path, "export const baselineTest = true;\n")
        self.commit = "0123456789abcdef0123456789abcdef01234567"
        self.baseline_files = {
            path.relative_to(self.source).as_posix(): path.read_bytes()
            for path in self.source.rglob("*")
            if path.is_file()
        }
        self._write_bytes(self.overlay_path, self.overlay_data)
        self.overlay_manifest = self.root / "overlay.json"
        self.overlay_manifest.write_text(json.dumps({
            "schema_version": 1,
            "baseline_ref": self.commit[:10],
            "license": "AGPL-3.0-only",
            "files": [{
                "path": self.overlay_path,
                "sha256": hashlib.sha256(self.overlay_data).hexdigest(),
                "test": True,
            }],
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write(self, relative: str, content: str) -> None:
        self._write_bytes(relative, content.encode("utf-8"))

    def _write_bytes(self, relative: str, content: bytes) -> None:
        path = self.source / Path(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def _entries(self, archive_path: Path) -> dict[str, bytes]:
        with tarfile.open(archive_path, "r:gz") as archive:
            result: dict[str, bytes] = {}
            for member in archive.getmembers():
                if member.isfile():
                    stream = archive.extractfile(member)
                    assert stream is not None
                    result[member.name.removeprefix("readweave-source/")] = stream.read()
            return result

    def _archive_head(self, _source: Path, archive_path: Path) -> None:
        with tarfile.open(archive_path, "w:") as archive:
            for relative, data in sorted(self.baseline_files.items()):
                info = tarfile.TarInfo(relative)
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                archive.addfile(info, io.BytesIO(data))

    def _build_archive(self, output: Path) -> dict[str, object]:
        with (
            patch.object(package_source, "_git_commit", return_value=self.commit),
            patch.object(package_source, "_archive_head", side_effect=self._archive_head),
        ):
            return package_source.build_source_archive(self.source, output, self.overlay_manifest)

    def test_archive_is_curated_sanitized_and_reproducible(self) -> None:
        first = self.root / "first.tar.gz"
        second = self.root / "second.tar.gz"
        result = self._build_archive(first)
        self._build_archive(second)

        self.assertEqual(first.read_bytes(), second.read_bytes())
        entries = self._entries(first)
        self.assertIn("LICENSE", entries)
        self.assertIn("NOTICE", entries)
        self.assertEqual(json.loads(entries["contributors.json"]), {"contributors": []})
        self.assertIn("apps/server/src/assets/THIRD-PARTY-NOTICES.md", entries)
        self.assertIn(self.overlay_path, entries)
        self.assertIn("apps/client/src/client.ts", entries)
        self.assertIn("apps/server/src/server.ts", entries)
        self.assertIn("apps/server/src/assets/llm/prompts/base_system_prompt.md", entries)
        self.assertIn("apps/server/src/assets/readweave-writing-skill/SKILL.md", entries)
        self.assertTrue(all(path in entries for path in package_source.RUNTIME_SUPPORT_FILES if path.endswith(".md")))
        self.assertNotIn("apps/server/src/assets/other/internal-notes.md", entries)
        self.assertIn("apps/server/docker/package.json", entries)
        self.assertIn("apps/server/docker/pnpm-workspace.yaml", entries)
        self.assertNotIn("apps/server/docker/traefik/compose.yml", entries)
        self.assertIn("packages/commons/src/index.ts", entries)
        self.assertIn("packages/trilium-core/src/test/becca_easy_mocking.ts", entries)
        self.assertIn("packages/trilium-core/src/test/becca_mocking.ts", entries)
        self.assertIn("apps/desktop/package.json", entries)
        self.assertNotIn("apps/desktop/src/private.ts", entries)
        self.assertNotIn("packages/trilium-e2e/src/private.ts", entries)
        self.assertNotIn(".private/secrets.json", entries)
        self.assertNotIn("apps/client/.env.local", entries)
        self.assertNotIn("apps/client/node_modules/pkg/index.js", entries)
        self.assertNotIn("evals/case.json", entries)
        self.assertNotIn("docs/private.md", entries)

        root_package = json.loads(entries["package.json"])
        self.assertEqual(set(root_package["scripts"]), {"client:build", "server:build"})
        self.assertNotIn("email", root_package["author"])
        npmrc = entries[".npmrc"].decode("utf-8")
        self.assertEqual(npmrc, "save-prefix=^\n")

        manifest = json.loads(entries["SOURCE-MANIFEST.json"])
        digest = manifest.pop("manifest_sha256")
        self.assertEqual(digest, hashlib.sha256(package_source._canonical_json(manifest)).hexdigest())
        self.assertEqual(result["manifest_sha256"], digest)
        self.assertEqual(
            manifest["build_commands"]["install"],
            "corepack pnpm install --frozen-lockfile --ignore-scripts",
        )
        self.assertIn(
            "packages/trilium-core/src/test/becca_mocking.ts",
            manifest["build_support_files"],
        )
        self.assertIn("apps/server/docker/pnpm-workspace.yaml", manifest["runtime_support_files"])
        self.assertIn(
            "apps/server/src/assets/readweave-writing-skill/SKILL.md",
            manifest["runtime_support_files"],
        )
        self.assertIn(
            {"path": "contributors.json", "actions": ["contributor_identity_records_removed"]},
            manifest["transformations"],
        )
        records = {entry["path"]: entry for entry in manifest["files"]}
        self.assertEqual(records[self.overlay_path]["sha256"], hashlib.sha256(self.overlay_data).hexdigest())
        sidecar = first.with_name(first.name + ".sha256").read_text(encoding="ascii")
        self.assertTrue(sidecar.startswith(hashlib.sha256(first.read_bytes()).hexdigest()))

    def test_overlay_hash_mismatch_stops_packaging(self) -> None:
        self._write_bytes(self.overlay_path, b"changed after manifest\n")
        with self.assertRaisesRegex(package_source.PackageError, "哈希与 manifest 不一致"):
            self._build_archive(self.root / "bad.tar.gz")

    def test_overlay_rejects_absolute_and_parent_paths(self) -> None:
        for path in ("../escape.ts", "C:/Users/test/private.ts", "/tmp/private.ts"):
            manifest = json.loads(self.overlay_manifest.read_text(encoding="utf-8"))
            manifest["files"][0]["path"] = path
            self.overlay_manifest.write_text(json.dumps(manifest), encoding="utf-8")
            with self.subTest(path=path), self.assertRaises(package_source.PackageError):
                self._build_archive(self.root / "bad.tar.gz")
        self.overlay_manifest.write_text(json.dumps({
            "schema_version": 1,
            "baseline_ref": self.commit[:10],
            "license": "AGPL-3.0-only",
            "files": [{
                "path": self.overlay_path,
                "sha256": hashlib.sha256(self.overlay_data).hexdigest(),
                "test": True,
            }],
        }), encoding="utf-8")

    def test_bundled_user_guide_redacts_local_absolute_paths(self) -> None:
        path = "apps/server/src/assets/doc_notes/en/User Guide/Data directory.html"
        original = b'<p>C:\\Users\\private-user\\AppData\\Roaming\\ReadWeave</p>'
        sanitized, actions = package_source._sanitize(path, original)
        self.assertIn("absolute_user_paths_redacted", actions)
        self.assertNotIn(b"C:\\Users\\private-user", sanitized)
        package_source._scan_payload(path, sanitized)

    def test_credential_scanner_allows_only_generic_auth_url_comments(self) -> None:
        package_source._scan_payload(
            "apps/server/src/services/safe_fetch.ts",
            b"// `https://user:pass@host/` is a documentation example.\n",
        )
        with self.assertRaisesRegex(package_source.PackageError, "疑似凭据内容"):
            package_source._scan_payload(
                "apps/server/src/services/safe_fetch.ts",
                b'const url = "https://account:secret@service.invalid/";\n',
            )

    def test_source_comments_redact_machine_specific_user_paths(self) -> None:
        path = "packages/commons/src/lib/electron_api_interface.ts"
        original = b"/** file:///C:/Users/private-user/AppData/example.pdf */\n"
        sanitized, actions = package_source._sanitize(path, original)
        self.assertIn("absolute_user_paths_redacted_from_comment", actions)
        self.assertNotIn(b"private-user", sanitized)
        package_source._scan_payload(path, sanitized)

    def test_enex_sample_redacts_attachment_origin_paths(self) -> None:
        path = "packages/trilium-core/src/services/import/samples/File with attachments.enex"
        original = b"<source-url>file:///C:/Users/private-user/Documents/note.txt</source-url>\n"
        sanitized, actions = package_source._sanitize(path, original)
        self.assertIn("absolute_user_paths_redacted_from_sample", actions)
        self.assertNotIn(b"private-user", sanitized)
        package_source._scan_payload(path, sanitized)


if __name__ == "__main__":
    unittest.main()
