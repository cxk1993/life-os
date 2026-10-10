"""内核接口版本与 kernelApi 兼容判断（总纲 §1.3.1 / 验收 #9）。

内核只暴露一组稳定接口，版本号随破坏性变更递增。
插件在 manifest.kernelApi 里声明它能接受的**内核接口版本范围**（caret 语义），
不兼容时明确拒绝加载，并给出人话原因，不许静默失败。

不引入 semver 依赖：caret 规则足够简单，自实现更可控、零新增依赖。
"""
from __future__ import annotations

# 当前内核对外暴露的接口版本。内核破坏性变更时由 T03 递增此值。
KERNEL_API_VERSION = "1.0.0"


def _parse(version: str) -> tuple[int, int, int]:
    """把 "1.2.3" 解析成 (1, 2, 3)。非标准格式抛 ValueError。"""
    parts = version.split(".")
    if len(parts) not in (1, 2, 3):
        raise ValueError(f"版本号格式应为 主.次[.修订]：{version!r}")
    nums: list[int] = []
    for p in parts:
        if not p.isdigit():
            raise ValueError(f"版本号片段必须是数字：{version!r}")
        nums.append(int(p))
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def meets_min_kernel(min_kernel: str, kernel_version: str = KERNEL_API_VERSION) -> bool:
    """★ 判断内核版本是否 **≥** 插件声明的 `minKernel`（最低版本语义）。

    ★ 2026-09-25（发现）：此前 `discover.py` 把 `minKernel`
      交给 `satisfies()` 判断，而 `satisfies` 是 **caret/精确** 语义 ——
      于是 `minKernel="0.1.0"` 在 1.0.0 内核上被判**不满足**（且 `f"={...}"`
      的 `=` 前缀还会让 `_parse` 抛异常），**所有声明 0.1.0 的第三方插件
      一律 degraded → 跳过激活 → 路由不挂载**。

    `minKernel` 的语义是"至少要哪个内核" —— 就是 `>=`，与 caret 是两回事。
    """
    try:
        cur = _parse(kernel_version)
        want = _parse(min_kernel)
    except ValueError:
        return False
    return cur >= want


def satisfies(kernel_api_range: str, kernel_version: str = KERNEL_API_VERSION) -> bool:
    """判断内核版本是否满足插件的 kernelApi 声明（caret 语义）。

    "^1"      -> >=1.0.0 且 <2.0.0
    "^1.2"    -> >=1.2.0 且 <2.0.0
    "^1.2.3"  -> >=1.2.3 且 <2.0.0
    "1.0.0"   -> 精确等于（兼容无 ^ 的写法）
    """
    rng = kernel_api_range.strip()
    if not rng:
        return False

    exact = rng
    if rng.startswith("^"):
        exact = rng[1:]
        caret = True
    else:
        caret = False

    try:
        want_major, want_minor, want_patch = _parse(exact)
    except ValueError:
        return False
    try:
        cur_major, cur_minor, cur_patch = _parse(kernel_version)
    except ValueError:
        return False

    if caret:
        # 同主版本，且 >= 声明的最低版本
        return cur_major == want_major and (cur_minor, cur_patch) >= (want_minor, want_patch)

    # 精确匹配
    return (cur_major, cur_minor, cur_patch) == (want_major, want_minor, want_patch)


def check_compatibility(kernel_api_range: str, kernel_version: str = KERNEL_API_VERSION) -> None:
    """不兼容时抛人话异常（供加载器在启动/安装时调用）。"""
    if not satisfies(kernel_api_range, kernel_version):
        raise IncompatibleKernelApiError(
            f"插件要求内核接口 {kernel_api_range!r}，但当前内核接口版本为 "
            f"{kernel_version!r}。请升级内核或降级插件——内核不会静默加载不兼容的插件。"
        )


class IncompatibleKernelApiError(Exception):
    """kernelApi 不兼容：加载器必须据此明确拒绝加载。"""
