"""AST-D 段三 · 第三方插件生命周期端到端（真实 install / uninstall，非 fixture）。

★ 为什么这份测试存在：全仓此前从未有过一个真实的第三方插件，
  `manager.install()` 与 `manager.uninstall()` 这两个"只对 third-party 开放"的入口
  没有过真样本可跑（2026-09-23 取证：全仓 `third` 在测试里仅 9 处命中，
  `test_plugins.py` 用的是合成 fixture 目录）。首单 增强了生成器，
  这一单就把生成器造出来的东西**从头装一遍再从头卸一遍**。

★★ 安全红线（先读这段再改这个文件）：
  `core/plugins/manager.py:221-222` —— uninstall 的第 5 步是
      `shutil.rmtree(info.directory)`，**会把插件目录整个删掉**。
  所以本测试**绝不允许对 `plugins/countdown/` 本体执行 uninstall**：
  做法是把原件整目录复制成一个带随机后缀的副本（id / api.base / 表名 / 模型缓存键
  一并改写，保持"表名以插件 id 为前缀"的组内约定），**让副本去死，原件活著**。

跑法（cwd 必须是 services/api，与门禁一致）：
    cd services/api && python3 -m pytest ../../plugins/countdown/tests -q
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

_API = Path(__file__).resolve().parents[3] / "services" / "api"
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from core.app import create_app  # noqa: E402
from core.security import create_access_token  # noqa: E402
from db.engine import get_engine, init_engine  # noqa: E402

LIFE_ROOT = Path(__file__).resolve().parents[3]
PLUGINS_DIR = LIFE_ROOT / "plugins"
SRC = PLUGINS_DIR / "countdown"

AUTH = {"Authorization": f"Bearer {create_access_token('admin')}"}


def _clone(dst_id: str) -> Path:
    """把真实插件复制成一个 id 不同的副本，并把它内部所有 id 相关字面量同步改写。"""
    dst = PLUGINS_DIR / dst_id
    shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    man = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    man["id"] = dst_id
    man["api"] = {
        "base": f"/api/v1/{dst_id}",
        "openapi": f"/api/v1/{dst_id}/openapi.json",
        "health": f"/api/v1/{dst_id}/health",
    }
    (dst / "manifest.json").write_text(
        json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    table = f"{dst_id.replace('-', '_')}_item"
    key = f"{dst_id.replace('-', '_')}_models"
    for rel in ("api/models.py", "api/router.py", "api/migrations/0001_init.py"):
        p = dst / rel
        s = p.read_text(encoding="utf-8")
        s = s.replace('"countdown_item"', f'"{table}"').replace('"countdown_models"', f'"{key}"')
        p.write_text(s, encoding="utf-8", newline="\n")
    return dst


@pytest.fixture
def e2e() -> Iterator[tuple[str, Path]]:
    """副本插件目录；用完兜底删除（uninstall 正常时应已自删）。"""
    dst_id = f"cdx-{uuid.uuid4().hex[:6]}"
    dst = _clone(dst_id)
    try:
        yield dst_id, dst
    finally:
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """独立引擎 + 独立 SQLite（与 tests/test_plugins.py 同一姿势，避免跨测试串库）。"""
    import db.engine as _db_engine_mod

    _db_engine_mod._engine = None
    engine = init_engine(f"sqlite:///{tmp_path / 'e2e.db'}")
    SQLModel.metadata.create_all(engine)
    yield TestClient(create_app())


class TestThirdPartyLifecycle:
    """discover → install → 建表 → 调端点 → disable → enable → uninstall → 清理干净。"""

    def test_full_lifecycle(self, client: TestClient, e2e: tuple[str, Path]) -> None:
        dst_id, dst = e2e
        base = f"/api/v1/{dst_id}"
        table = f"{dst_id.replace('-', '_')}_item"

        # ── ① discover：未安装的第三方插件应被"发现"但不在已挂载态 ─────────────
        listed = client.get("/api/v1/plugins", headers=AUTH)
        assert listed.status_code == 200, listed.text
        names = [p["id"] for p in listed.json()["plugins"]]
        assert dst_id in names, f"副本未被 discover 发现：{names[:8]}…"
        one = client.get(f"/api/v1/plugins/{dst_id}", headers=AUTH)
        assert one.status_code == 200, one.text
        # ★ 真实形状：清单项是【平铺】的（id/name/version/kind/source/enabled/permissions/
        #   slots/provides/requires/last_error/valid），**不含 manifest 键**。
        #   —— 最初按前端 types.ts 的 PluginInfo.manifest 假设了形状，才在首跑吃这条红。
        assert one.json()["kind"] == "third-party"
        assert one.json()["source"] == "third-party"
        # ★ 原件也在（真插件），顺带确认它能被发现——dock 可见性问题的前半段
        assert "countdown" in names

        # ── ② install（全仓第一次对真实第三方插件走这个入口）────────────────
        inst = client.post("/api/v1/plugins/install", json={"id": dst_id}, headers=AUTH)
        assert inst.status_code == 200, inst.text
        body = inst.json()
        assert body.get("enabled") is True, body

        # ── ③ 迁移真建表 ───────────────────────────────────────────────
        from sqlalchemy import inspect

        assert inspect(get_engine()).has_table(table), f"迁移未建表：{table}"

        # ── ④ 端点可用（挂载生效）──────────────────────────────────────
        assert client.get(f"{base}/health", headers=AUTH).json() == {"ok": True}

        created = client.post(
            f"{base}/items",
            json={
                "title": "唤醒日",
                "target_date": "2020-06-27",
                "kind": "anniversary",
                "note": "e2e",
            },
            headers=AUTH,
        )
        assert created.status_code == 201, created.text
        item = created.json()
        assert item["days_left"] >= 0 and item["is_past"] is False
        assert item["next_date"].startswith(str(item["next_date"])[:4])

        items = client.get(f"{base}/items", headers=AUTH)
        assert items.status_code == 200 and len(items.json()) == 1

        # 非法 kind 必须被服务层拒（走 RFC7807）
        bad = client.post(
            f"{base}/items",
            json={"title": "x", "target_date": "2030-01-01", "kind": "weird"},
            headers=AUTH,
        )
        assert bad.status_code in (400, 422), bad.text

        # ★ 远期倒数日（>1 年）也要能进 landmarks —— 段三抓出的设计缺陷回归
        #（段二初版本地校验写了 le=365，"毕业还有 800 天"这类永远查不到）
        from datetime import date as _d
        from datetime import timedelta as _td

        far = (_d.today() + _td(days=800)).isoformat()
        assert (
            client.post(
                f"{base}/items",
                json={"title": "远期", "target_date": far, "kind": "countdown"},
                headers=AUTH,
            ).status_code
            == 201
        )

        # 不存在的 id → 404
        assert client.get(f"{base}/items/no-such-id", headers=AUTH).status_code == 404

        # ── ⑤ /landmarks（N1 接口，豆包 sidecar 第二例要消费的）──────────
        lm = client.get(f"{base}/landmarks", params={"window": 3650}, headers=AUTH)
        assert lm.status_code == 200, lm.text
        rows = lm.json()
        assert any(r["title"] == "唤醒日" and r["days_until"] >= 0 for r in rows), rows
        assert any(r["title"] == "远期" and 790 <= r["days_until"] <= 800 for r in rows), (
            f"远期倒数日应出现在 window=3650 内：{[r['title'] for r in rows]}"
        )
        # ★ 排序契约：days_until 升序
        assert [r["days_until"] for r in rows] == sorted(r["days_until"] for r in rows)

        # ── ⑥ 跨插件调用（ISSUE-005 A 案）· ★ 实测：第三方插件【用不了】────────
        # 根因（2026-09-23 实证）：core/deps.py::_caller_plugin_id 靠
        #   request.app.state.modules 反查 caller，而该注册表在 create_app 里
        #   只登记内置模块 —— 探针实测 18 条全为 builtin/core，
        #   新装的第三方（含本插件副本）【不在其中】→ 永远识别不出 caller → 403。
        # 所以这里断言的是【平台现状】而不是【本插件失败】：
        #   一旦注册表纳入第三方，本断言会红，那时改成 200 并撤帖内"提醒碑"。
        cross = client.get(f"{base}/example-cross-plugin", headers=AUTH)
        assert cross.status_code == 403, (
            f"跨插件授权行为已变，请同步取证帖：{cross.status_code} {cross.text}"
        )
        assert "无法识别调用方插件" in cross.text, cross.text

        # ★ 同源的第二个症状：能力地图 /api/v1/modules 也看不到第三方插件
        mods = client.get("/api/v1/modules", headers=AUTH)
        if mods.status_code == 200:  # ISSUE-011 案 C 落地前后都跑得通
            ids = [m.get("id") for m in mods.json().get("modules", [])]
            assert dst_id not in ids, f"★ 第三方已进能力地图（取证可撤）：{ids}"

        # ── ⑦ disable 摘路由 → enable 挂回（注册表与运行时分离）──────────
        assert client.post(f"/api/v1/plugins/{dst_id}/disable", headers=AUTH).status_code == 200
        assert client.get(f"{base}/items", headers=AUTH).status_code == 404, "disable 后路由仍在"
        assert client.post(f"/api/v1/plugins/{dst_id}/enable", headers=AUTH).status_code == 200
        assert client.get(f"{base}/items", headers=AUTH).status_code == 200, "enable 后路由未恢复"

        # ── ⑧ uninstall：表 / 状态 / 目录 三清（★ 全仓第一次真发生）──────
        un = client.post(f"/api/v1/plugins/{dst_id}/uninstall", headers=AUTH)
        assert un.status_code == 200, un.text
        assert un.json().get("uninstalled") is True
        assert not dst.exists(), "★ uninstall 未删除插件目录"
        assert not inspect(get_engine()).has_table(table), "★ uninstall 未回滚建表"
        after = client.get("/api/v1/plugins", headers=AUTH).json()["plugins"]
        assert dst_id not in [p["id"] for p in after], "★ uninstall 后 plugin_state 残留"

        # 原件必须活著——本测试的红线（防 rmtree 误删源码）
        assert (SRC / "manifest.json").exists(), "★★ 原件被误删，立即停止并上报"


class TestDockVisibility:
    """段三附带问题：entry="" 的纯 API 插件，会不会在 dock 里留一个点不开的图标？

    只能证明后端侧的形状（有没有 entry / enabled 字段可让前端判断），
    真正的渲染结论要 或 在前端看一眼（见完工帖提问）。
    """

    def test_清单已含manifest_ISSUE012验收断言(
        self, client: TestClient, e2e: tuple[str, Path]
    ) -> None:
        """★ 2026-09-23 晚间改红为绿（原「提醒碑」）：12:48《取证帖》指出的
        「清单项缺 manifest → 前端 `p.manifest.entry` 必崩 → 插件扩展点贡献无法挂载」
        已由 **/ ISSUE-012** 修复（后端 `list_plugins()` 补 manifest 键 + 前端防御）。

        本测试现在**正面验收 ISSUE-012**：清单项必须含 `manifest`，
        且前端真正要用的三个键（`entry` / `window` / `slots`）都能从响应里读到。
        → 若哪天回退，本测试立刻红（守卫意义保留）。
        """
        dst_id, _ = e2e
        data = client.get("/api/v1/plugins", headers=AUTH).json()
        mine = [p for p in data["plugins"] if p.get("id") == dst_id]
        assert mine, (
            f"清单里应能发现未安装的第三方插件，实到：{[p.get('id') for p in data['plugins']][:8]}"
        )
        p = mine[0]
        assert p["source"] == "third-party" and p["kind"] == "third-party"
        assert "enabled" in p and "slots" in p, p.keys()
        assert p["slots"] == [], "V1 纯 API 插件不应声明任何扩展点"

        # ★ ISSUE-012 验收点：manifest 在，且前端三键可读
        assert "manifest" in p, f"ISSUE-012 回退：清单项又缺 manifest（keys={sorted(p)}）"
        man = p["manifest"]
        for key in ("entry", "window", "slots"):
            assert key in man, f"前端要用的 manifest.{key} 读不到：{sorted(man)}"
        assert man["entry"] == "", "V1 纯 API 插件的 entry 必须是空串（前端据此跳过入口加载）"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
