"""create_plugin.py 脚手架生成器测试（TX-AST-01）。

覆盖验收判据：
  - 脚手架能生成 third-party / builtin 骨架（文件齐全）
  - 非法 id 拒错（exit 2）
  - manifest 必填字段校验：缺字段/格式错 → 精确报错
  - permissions 声明式权限：数组格式校验（TX-PERM-01 A 路径回退）
  - --with-example：router 含跨插件调用示例（ISSUE-005 C 案参考）

不依赖 DB；输出目录全部重定向到 tmp_path，不污染仓库。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "create_plugin.py"


def _load_module() -> object:
    spec = importlib.util.spec_from_file_location("create_plugin", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def cp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """加载 create_plugin 模块，并把输出目录重定向到临时目录。"""
    mod = _load_module()
    mod._PLUGINS_DIR = tmp_path / "plugins"
    mod._BUILTIN_API_DIR = tmp_path / "modules"
    mod._BUILTIN_WEB_DIR = tmp_path / "web"
    return mod


def _read_manifest(root: Path, kind: str, pid: str) -> dict:
    base = root / "modules" if kind == "builtin" else root / "plugins"
    return json.loads((base / pid / "manifest.json").read_text(encoding="utf-8"))


# ── 1. 骨架生成 ──

def test_generate_third_party_files(cp, tmp_path):
    rc = cp.main(["hello-bot", "你好机器人"])
    assert rc == 0
    root = tmp_path / "plugins" / "hello-bot"
    for rel in ("manifest.json", "README.md", "api/router.py", "api/models.py",
                "api/settings.schema.json", "api/migrations/0001_init.py", "web/index.tsx"):
        assert (root / rel).is_file(), f"缺少 {rel}"


def test_generate_builtin_files(cp, tmp_path):
    rc = cp.main(["inner-plug", "内置插件", "--kind", "builtin"])
    assert rc == 0
    assert (tmp_path / "modules" / "inner-plug" / "router.py").is_file()
    assert (tmp_path / "web" / "inner-plug" / "index.tsx").is_file()


# ── 2. id 校验 ──

@pytest.mark.parametrize("bad_id", ["Bad_ID!", "1abc", "a--b", "a-b-" + "x" * 40])
def test_invalid_id_rejected(cp, bad_id):
    assert cp.main([bad_id, "非法id"]) == 2


def test_valid_id_accepted(cp):
    assert cp.main(["my-notes", "我的笔记"]) == 0


# ── 3. manifest 必填字段校验 ──

def test_generated_manifest_passes_validate(cp, tmp_path):
    cp.main(["hello-bot", "你好机器人"])
    mf = _read_manifest(tmp_path, "third-party", "hello-bot")
    assert cp._validate_manifest(mf) == []


def test_manifest_missing_field_rejected(cp):
    good = {
        "id": "x", "name": "x", "version": "0.1.0", "kind": "third-party",
        "kernelApi": "^1", "api": {}, "provides": [], "requires": [],
        "slots": [], "emits": [], "consumes": [], "permissions": [],
    }
    bad = dict(good)
    bad.pop("permissions")
    errs = cp._validate_manifest(bad)
    assert any("permissions" in e for e in errs)


def test_manifest_bad_kind_rejected(cp):
    mf = {"id": "x", "name": "x", "version": "0.1.0", "kind": "hacker",
          "kernelApi": "^1", "api": {}, "provides": [], "requires": [],
          "slots": [], "emits": [], "consumes": [], "permissions": []}
    assert any("kind" in e for e in cp._validate_manifest(mf))


# ── 4. permissions 声明式权限（TX-PERM-01 A 路径数组格式）──

def test_permissions_is_list_of_str(cp, tmp_path):
    cp.main(["hello-bot", "你好机器人"])
    mf = _read_manifest(tmp_path, "third-party", "hello-bot")
    assert isinstance(mf["permissions"], list)
    assert all(isinstance(p, str) for p in mf["permissions"])


def test_permissions_non_list_rejected(cp):
    mf = {"id": "x", "name": "x", "version": "0.1.0", "kind": "third-party",
          "kernelApi": "^1", "api": {}, "provides": [], "requires": [],
          "slots": [], "emits": [], "consumes": [], "permissions": {"db": "own"}}
    assert any("permissions" in e for e in cp._validate_manifest(mf))


def test_permissions_non_str_element_rejected(cp):
    mf = {"id": "x", "name": "x", "version": "0.1.0", "kind": "third-party",
          "kernelApi": "^1", "api": {}, "provides": [], "requires": [],
          "slots": [], "emits": [], "consumes": [], "permissions": ["db:own", 42]}
    assert any("permissions" in e for e in cp._validate_manifest(mf))


# ── 5. --with-example 跨插件调用示例（ISSUE-005 C 案）──

def test_with_example_router_contains_cross_plugin(cp, tmp_path):
    cp.main(["hello-bot", "你好机器人", "--with-example"])
    router = (tmp_path / "plugins" / "hello-bot" / "api" / "router.py").read_text(encoding="utf-8")
    assert "example-cross-plugin" in router
    assert "get_plugin_client" in router


def test_default_router_no_example(cp, tmp_path):
    cp.main(["hello-bot", "你好机器人"])
    router = (tmp_path / "plugins" / "hello-bot" / "api" / "router.py").read_text(encoding="utf-8")
    assert "example-cross-plugin" not in router
    assert "def health" in router


# ── 6. 生成物卫生 ──

def test_generated_manifest_has_required_fields(cp, tmp_path):
    cp.main(["hello-bot", "你好机器人"])
    mf = _read_manifest(tmp_path, "third-party", "hello-bot")
    for field in ("id", "name", "version", "kind", "kernelApi", "api",
                  "provides", "requires", "slots", "emits", "consumes", "permissions"):
        assert field in mf, f"缺必填字段 {field}"
