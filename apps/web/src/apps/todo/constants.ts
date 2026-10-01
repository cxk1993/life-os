/**
 * todo 模块共享常量（★ 2026-10-02 · 主人令「已完成满 7 天归档」）。
 *
 * ⚠️ 这个数字是**后端**定的（`services/api/modules/todo/service.py` 的
 *   `ARCHIVE_AFTER_DAYS`），前端只用来**显示文案**——别在这里改它来「调归档」，
 *   改了也不生效（判据在后端 SQL 里），只会让界面说的和实际做的不一致。
 *   后端有测试（`test_archive_threshold_is_seven_days`）钉住这个数，
 *   真要调整请改后端并同步这里。
 */
export const ARCHIVE_AFTER_DAYS = 7;
