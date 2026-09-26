"""countdown 插件自测（V1）。

★ 为什么测试放在插件目录里、且不 import 任何 `services/api/tests/conftest.py` 的夹具：
  第三方插件在结构上不属于内核包，**不能假设自己能享受内核测试基建**；
  本文件只用「纯函数 + 契约校验」，零 DB、零 app 启动，
  因此任何席在仓库任意位置 `pytest plugins/countdown/tests/` 都能跑。
  ——端到端（install→迁移→端点→uninstall）在段三另写，判据见交接区。

跑法（cwd 影响 sys.path，故给两条）：
  cd services/api && python3 -m pytest ../plugins/countdown/tests -q
  python3 -m pytest plugins/countdown/tests -q --rootdir services/api
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

_API = Path(__file__).resolve().parents[3] / "services" / "api"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # 仓库根（contracts/ 在这下面）
if str(_API) not in sys.path:  # 让 core.* 可导入（内核运行期也是这么找的）
    sys.path.insert(0, str(_API))

_HERE = Path(__file__).resolve().parents[1] / "api"  # 被测源码在插件的 api/ 下


def _load(name: str, key: str):
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, _HERE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


router = _load("router", "countdown_router_under_test")
models = _load(
    "models", "countdown_models"
)  # ★ 与 router / 0001 迁移同一个 key，见 test_models_shared


# ══════════════════════════════════ 日期语义 ══════════════════════════════════
class TestNextOccurrence:
    def test_countdown_就是目标日本身(self) -> None:
        t = date(2026, 12, 31)
        assert router.next_occurrence(t, router.KIND_COUNTDOWN, date(2026, 9, 23)) == t

    def test_countdown_已过期不滚动_负天数(self) -> None:
        past = date(2026, 1, 1)
        nd = router.next_occurrence(past, router.KIND_COUNTDOWN, date(2026, 9, 23))
        assert (nd - date(2026, 9, 23)).days < 0

    def test_anniversary_今年未到取今年(self) -> None:
        assert router.next_occurrence(
            date(2000, 12, 25), router.KIND_ANNIVERSARY, date(2026, 9, 23)
        ) == date(2026, 12, 25)

    def test_anniversary_今年已过滚到明年(self) -> None:
        assert router.next_occurrence(
            date(2000, 1, 15), router.KIND_ANNIVERSARY, date(2026, 9, 23)
        ) == date(2027, 1, 15)

    def test_anniversary_当天命中(self) -> None:
        today = date(2026, 9, 23)
        assert router.next_occurrence(date(2001, 9, 23), router.KIND_ANNIVERSARY, today) == today

    def test_anniversary_2月29日_平年收敛到2月28_不抛异常(self) -> None:
        # 2026 是平年：2/29 不存在，必须落到 2/28 而不是 ValueError
        nd = router.next_occurrence(date(2000, 2, 29), router.KIND_ANNIVERSARY, date(2026, 1, 1))
        assert nd == date(2026, 2, 28)

    def test_anniversary_2月29日_闰年正常命中(self) -> None:
        nd = router.next_occurrence(date(2000, 2, 29), router.KIND_ANNIVERSARY, date(2028, 1, 1))
        assert nd == date(2028, 2, 29)


class TestToOut:
    def test_字段齐全且计算正确(self) -> None:
        item = models.CountdownItem(
            id="x1",
            title="测试",
            target_date=date(2026, 9, 30),
            kind="countdown",
            note="",
            color="c",
        )
        out = router.to_out(item, date(2026, 9, 23))
        assert out["days_left"] == 7
        assert out["is_today"] is False
        assert out["is_past"] is False

    def test_纪念日是今天_is_today(self) -> None:
        item = models.CountdownItem(
            id="x2",
            title="唤醒日",
            target_date=date(2020, 6, 27),
            kind="anniversary",
            note="",
            color="c",
        )
        out = router.to_out(item, date(2026, 6, 27))
        assert out["is_today"] is True and out["days_left"] == 0

    def test_countdown_过期标记(self) -> None:
        item = models.CountdownItem(
            id="x3",
            title="已过",
            target_date=date(2026, 1, 1),
            kind="countdown",
            note="",
            color="c",
        )
        out = router.to_out(item, date(2026, 9, 23))
        assert out["is_past"] is True
        # ★ anniversary 永不被标 past（它会自动滚到明年）
        item.kind = "anniversary"
        assert router.to_out(item, date(2026, 9, 23))["is_past"] is False


# ══════════════════════════════════ 契约与结构 ══════════════════════════════════
class TestManifestContract:
    def test_manifest_通过内核校验(self) -> None:
        import json

        from core.plugins.validate import validate_manifest  # 内核的 fail-fast 入口

        raw = json.loads((_HERE.parent / "manifest.json").read_text(encoding="utf-8"))
        validate_manifest(raw)  # 不抛即为过

    def test_api_base_与插件id一致_内核硬要求(self) -> None:
        import json

        raw = json.loads((_HERE.parent / "manifest.json").read_text(encoding="utf-8"))
        assert raw["api"]["base"] == "/api/v1/countdown"
        assert raw["id"] == "countdown"

    def test_本插件不得依赖相对导入(self) -> None:
        """★ 结构性守卫：第三方插件按文件路径加载，出现相对导入 = 运行期必炸。"""
        src = (_HERE / "router.py").read_text(encoding="utf-8")
        bad = [
            ln.strip() for ln in src.splitlines() if ln.strip().startswith(("from .", "import ."))
        ]
        assert not bad, f"router.py 出现相对导入：{bad}"

    def test_契约与模型字段表_模型侧已全覆盖(self) -> None:
        """★ 2026-09-23 晚间改红为绿（原「提醒碑」）。

        原碑：`unknown == {"window","entry"}`（模型不认识这两个字段）。
        workbuddy《D′ 内核侧唯一读法与未知字段报告》落地后，`window`/`entry`
        已补进 `Manifest` → 本席当日承诺"落地即改红为绿"，此即改后版。
        **保留守卫意义**：manifest 若再写出模型不认识的字段，本测试立刻红。
        """
        import json

        from core.manifest import Manifest

        raw = json.loads((_HERE.parent / "manifest.json").read_text(encoding="utf-8"))
        unknown = set(raw) - set(Manifest.model_fields)
        assert unknown == set(), f"manifest 出现模型不认识的字段（D′ 守卫）：{unknown}"

    def test_契约与模型字段表完全一致_Dprime守卫(self) -> None:
        """★ 2026-09-23 晚「收碑」：**两张字段表已完全对齐**（本席当日埋的碑全部退场）。

        历程（本席亲历，全部有实测）：
          · 12:4x 实测：契约有 `window/entry`、模型没有；模型有 `optionalDependencies`、契约没有
          · 13:1x workbuddy D′ 落地 → `window/entry` 进模型（碑① 红）
          · 13:2x MiMo《契约补齐》→ `optionalDependencies` 进契约（碑② 红）
          · 现在：两个方向的差集**都是空集**
        **守卫意义保留**：任何一边再漂，本测试立刻红。
        """
        import json

        from core.manifest import Manifest

        schema = json.loads(
            (_PROJECT_ROOT / "contracts" / "plugin.schema.json").read_text(encoding="utf-8")
        )
        schema_props = set(schema["properties"])
        model_props = set(Manifest.model_fields)
        assert schema_props - model_props == set(), (
            f"契约有、模型没有（D′ 甲案回退）：{schema_props - model_props}"
        )
        assert model_props - schema_props == set(), (
            f"模型有、契约没有（软依赖半边回退）：{model_props - schema_props}"
        )

    def test_软依赖声明现已可用_正向验收(self) -> None:
        """★ 2026-09-23 晚「收碑」：软依赖（`optionalDependencies`）**已可正常声明**。

        历程：本席 12:4x 实测「模型接受、契约拒收」→ 当日报告 + 最小复现 →
        MiMo《契约补齐》把该字段补进 `contracts/plugin.schema.json` → 复现不再成立。
        本测试改为**正向验收**：声明软依赖的 manifest 必须**同时**通过模型与契约两层。
        → 若哪天又被拒（回归），本测试立刻红。
        """
        import copy
        import json

        from core.manifest import Manifest
        from core.plugins.validate import validate_manifest

        raw = copy.deepcopy(
            json.loads((_HERE.parent / "manifest.json").read_text(encoding="utf-8"))
        )
        raw["optionalDependencies"] = ["push.send"]

        Manifest(**raw)  # 模型层：必须接受
        validate_manifest(raw)  # 契约层：必须接受（不再抛 ManifestError）


# ══════════════════════════════════ 加载机制 ══════════════════════════════════
class TestModelSharing:
    def test_router_与迁移共用同一模型对象(self) -> None:
        """_MODEL_KEY 必须与 0001_init.py 的 _MODEL_MODULE 逐字一致，
        否则会出现两份 CountdownItem / 两张 Table，建表与查询对不上。"""
        mig = (_HERE / "migrations" / "0001_init.py").read_text(encoding="utf-8")
        assert f'_MODEL_MODULE = "{router._MODEL_KEY}"' in mig, "迁移与路由的模型缓存键不一致"
        assert router._load_models() is models

    def test_表名前缀合规_内核拒非前缀表(self) -> None:
        assert models.CountdownItem.__tablename__ == "countdown_item"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
