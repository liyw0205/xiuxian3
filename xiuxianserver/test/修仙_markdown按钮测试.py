"""修仙 markdown 按钮协议测试。"""

from __future__ import annotations

from datetime import timedelta
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from 修仙.format_text import T
from 修仙.markdown_utils import MarkdownKeyboard, button, markdown_message_from_text
from 修仙.common import dump_json, now, ts
from 修仙.sql import XiuxianDB
from 修仙.修仙帮助.service import service as help_service
from 修仙.reply import _with_player_name


class FakeDB:
    """只给回复包装读取玩家头。"""

    def fetch_one(self, sql: str, *_args, **_kwargs) -> dict | None:
        if "FROM players AS p" in sql:
            return {"display_name": "青衫客", "title": "试剑人", "level": 19}
        if "FROM players" in sql:
            return {
                "status": "空闲",
                "hp": 100,
                "max_hp": 100,
                "mp": 60,
                "max_mp": 60,
                "rest_full_at": None,
                "rest_window_elapsed_seconds": 0,
            }
        return None


class BrokenNoticeDB(FakeDB):
    """玩家头正常，但通知查询异常时不能影响回复。"""

    def fetch_one(self, sql: str, *args, **kwargs) -> dict | None:
        if "FROM players AS p" in sql:
            return {"display_name": "青衫客", "title": "试剑人", "level": 19}
        raise RuntimeError("notice query failed")


class NoticeDB(FakeDB):
    """模拟多条通知，验证第二行和数量上限。"""

    def fetch_one(self, sql: str, params=(), *_args, **_kwargs) -> dict | None:
        if "FROM players AS p" in sql:
            return {"display_name": "青衫客", "title": "试剑人", "level": 19}
        if "FROM players" in sql:
            return {
                "status": "休息中",
                "hp": 0,
                "max_hp": 100,
                "mp": 0,
                "max_mp": 60,
                "rest_full_at": ts(now() + timedelta(minutes=29)),
                "rest_window_elapsed_seconds": 0,
            }
        if "FROM exploration_records" in sql:
            return {
                "started_at": ts(now() - timedelta(minutes=40)),
                "ready_at": ts(now() - timedelta(minutes=10)),
                "result": dump_json({"duration_seconds": 1800}),
            }
        if "seasonal_boss_participants" in sql:
            return {"ok": 1}
        if "wormhole_participants" in sql:
            return {"ok": 1}
        if "FROM sect_war_rewards" in sql:
            return {"ok": 1}
        if "duel_requests" in sql:
            return {"ok": 1}
        return None


def _real_notice_db() -> XiuxianDB:
    temp_dir = TemporaryDirectory()
    db = XiuxianDB(Path(temp_dir.name) / "notice_test.db")
    db._notice_temp_dir = temp_dir  # type: ignore[attr-defined]
    return db


def _close_real_notice_db(db: XiuxianDB) -> None:
    temp_dir = getattr(db, "_notice_temp_dir", None)
    db.close()
    if temp_dir is not None:
        temp_dir.cleanup()


def _seed_notice_player(db: XiuxianDB, client_id: str = "notice_ws") -> None:
    db.execute(
        """
        INSERT INTO players
        (client_id, display_name, level, exp, hp, max_hp, mp, max_mp, physique_id,
         physique_value, base_attack, defense, source_stones, status, location_name,
         x, y, backpack_limit, weight_limit, created_at)
        VALUES (?, '听雪客', 12, 0, 0, 100, 0, 60, 'fanti',
                0, 5, 0, 0, '空闲', '天枢城',
                0, 0, 80, 500, ?)
        """,
        (client_id, ts()),
    )


def _payload_content(payload: dict) -> str:
    return str(payload["message"]["content"])


def _payload_lines(payload: dict) -> list[str]:
    return _payload_content(payload).splitlines()


FakeExploreService = type("FakeExploreService", (), {"__module__": "修仙.探险.service"})


def test_button_default() -> None:
    """button("修仙信息") 默认 button_type 为 1。"""

    item = button("修仙信息")
    assert item["render_data"]["label"] == "修仙信息"
    assert item["action"]["type"] == 1
    assert item["action"]["data"] == "修仙信息"
    assert "enter" not in item["action"]


def test_keyboard_limit() -> None:
    """键盘最多 25 个按钮、每行最多 3 个。"""

    commands = [f"命令{i}" for i in range(1, 31)]
    keyboard = MarkdownKeyboard.from_commands(commands).to_content()
    rows = keyboard["content"]["rows"]
    assert len(rows) == 9
    assert all(len(row["buttons"]) <= 3 for row in rows)
    assert rows[-1]["buttons"][-1]["action"]["data"] == "命令25"


def test_plain_suggestion_uses_default_markdown_buttons() -> None:
    """没有 `<命令>` 时，也会因为默认按钮转成 markdown。"""

    message = markdown_message_from_text("普通提示。\n发送：修仙信息 查看状态")
    assert message is None

    payload = _with_player_name(
        "player_ws",
        {"code": 202, "type": "text", "message": "普通提示。\n发送：修仙信息 查看状态"},
        FakeDB(),
    )
    assert payload["type"] == "markdown"
    assert payload["message"]["content"].endswith("发送：修仙信息 查看状态")
    rows = payload["message"]["keyboard"]["content"]["rows"]
    assert [item["action"]["data"] for item in rows[0]["buttons"]] == ["指南", "状态", "修仙信息"]


def test_button_tags_to_markdown() -> None:
    """回复里的 `<命令>` 会转成按钮，正文不再显示尖括号标记。"""

    message = markdown_message_from_text("血气不足。\n可以先<休息>，也可以<修仙信息>")
    assert message is not None
    assert message["content"] == "血气不足。\n可以先，也可以"
    rows = message["keyboard"]["content"]["rows"]
    assert [item["action"]["data"] for item in rows[0]["buttons"]] == ["休息", "修仙信息"]


def test_button_tags_keep_command_text() -> None:
    """尖括号里的内容原样作为按钮命令，是否可用由业务自己决定。"""

    message = markdown_message_from_text("源石不足。\n请先<存入源石 数量>")
    assert message is not None
    rows = message["keyboard"]["content"]["rows"]
    assert rows[0]["buttons"][0]["action"]["data"] == "存入源石 数量"


def test_reply_text_with_button_tags_to_markdown() -> None:
    """统一回复出口遇到 `<命令>` 时自动升级为 markdown。"""

    payload = _with_player_name(
        "player_ws",
        {"code": 202, "type": "text", "message": "现在可以<探险状态><结束探险>"},
        FakeDB(),
    )
    assert payload["type"] == "markdown"
    assert "【青衫客·试剑人 Lv.19】" in payload["message"]["content"]
    assert "<探险状态>" not in payload["message"]["content"]
    rows = payload["message"]["keyboard"]["content"]["rows"]
    commands = [item["action"]["data"] for row in rows for item in row["buttons"]]
    assert commands == ["探险状态", "结束探险"]


def test_reply_keeps_long_handwritten_business_buttons() -> None:
    """业务手写按钮是明确入口页，不能被自动按钮目标数误截到 6 个。"""

    payload = _with_player_name(
        "player_ws",
        {"code": 202, "type": "text", "message": "请选择<cmd1><cmd2><cmd3><cmd4><cmd5><cmd6><cmd7><cmd8>"},
        FakeDB(),
    )
    commands = _payload_commands(payload)
    assert commands == [f"cmd{index}" for index in range(1, 9)]


def test_reply_header_notice_line_is_second_line() -> None:
    """通知显示在玩家头下一行，并限制最多三条。"""

    payload = _with_player_name(
        "player_ws",
        {"code": 202, "type": "text", "message": "正文"},
        NoticeDB(),
    )
    lines = _payload_lines(payload)
    assert lines[0] == "【青衫客·试剑人 Lv.19】"
    assert lines[1] == "🔴 通知：休息可结束｜探险可结束｜首领奖励待领"
    assert lines[2] == "正文"
    assert "虫洞奖励待领" not in lines[1]
    assert "对战请求待处理" not in lines[1]


def test_reply_header_notice_keeps_handwritten_buttons() -> None:
    """通知不使用尖括号，不破坏业务手写按钮优先级。"""

    payload = _with_player_name(
        "player_ws",
        {"code": 202, "type": "text", "message": "现在可以<探险状态><结束探险>"},
        NoticeDB(),
    )
    content = _payload_content(payload)
    assert "🔴 通知：" in content
    assert "<探险状态>" not in content
    commands = _payload_commands(payload)
    assert commands == ["探险状态", "结束探险"]


def test_reply_header_notice_not_used_for_predictive_buttons() -> None:
    """通知文字只展示，不参与正文预测按钮。"""

    payload = _with_player_name(
        "player_ws",
        {"code": 202, "type": "text", "message": "普通提示。"},
        NoticeDB(),
    )
    commands = _payload_commands(payload)
    assert commands == ["指南", "状态", "修仙信息"]


def test_reply_header_notice_failure_is_silent() -> None:
    """通知查询失败不影响正常回复。"""

    payload = _with_player_name(
        "player_ws",
        {"code": 202, "type": "text", "message": "普通提示。"},
        BrokenNoticeDB(),
    )
    content = _payload_content(payload)
    assert "【青衫客·试剑人 Lv.19】" in content
    assert "🔴 通知：" not in content
    assert content.endswith("普通提示。")


def test_reply_header_notice_from_real_tables() -> None:
    """用真实临时库覆盖重伤、探险和对战待处理。"""

    db = _real_notice_db()
    try:
        _seed_notice_player(db)
        db.execute(
            """
            INSERT INTO exploration_records
            (client_id, location_name, status, started_at, ready_at, result)
            VALUES (?, '青岚坊', '探险中', ?, ?, ?)
            """,
            (
                "notice_ws",
                ts(now() - timedelta(minutes=40)),
                ts(now() + timedelta(minutes=90)),
                dump_json({"duration_seconds": 60}),
            ),
        )
        db.execute(
            """
            INSERT INTO duel_requests
            (mode, from_client_id, to_client_id, stake, status, expires_at, created_at)
            VALUES ('spar', 'other_ws', 'notice_ws', 0, '等待', ?, ?)
            """,
            ((now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"), ts()),
        )
        payload = _with_player_name(
            "notice_ws",
            {"code": 202, "type": "text", "message": "查看状态"},
            db,
        )
        lines = _payload_lines(payload)
        assert lines[0] == "【听雪客·无 Lv.12】"
        assert lines[1] == "🔴 通知：重伤待休息｜探险可结束｜对战请求待处理"
        assert lines[2] == "查看状态"
    finally:
        _close_real_notice_db(db)


def test_hint_without_button_tags_uses_default_markdown_buttons() -> None:
    """T.hint 只负责提示格式；回复层统一补默认 markdown 按钮。"""

    text = T.hint("普通提示。", "发送：修仙信息 查看状态")
    assert text == "*普通提示。*\n发送：修仙信息 查看状态"

    payload = _with_player_name(
        "player_ws",
        {"code": 202, "type": "text", "message": text},
        FakeDB(),
    )
    assert payload["type"] == "markdown"
    assert payload["message"]["content"].endswith("发送：修仙信息 查看状态")
    rows = payload["message"]["keyboard"]["content"]["rows"]
    assert [item["action"]["data"] for item in rows[0]["buttons"]] == ["指南", "状态", "修仙信息"]


def test_predictive_buttons_from_content() -> None:
    """回复正文会预判下一步固定命令。"""

    payload = _with_player_name(
        "player_ws",
        {"code": 202, "type": "text", "message": "血气不足，建议先休息一下。"},
        FakeDB(),
    )
    commands = _payload_commands(payload)
    assert commands == ["休息", "结束休息", "状态"]
    assert len(commands) <= 6


def test_predictive_buttons_before_context_buttons() -> None:
    """预测按钮排在当前组件按钮之前，并按实际命令去重。"""

    payload = _with_player_name(
        "player_ws",
        {"code": 202, "type": "text", "message": "探险还没有到 30 分钟冷却，先查看预计算结果。"},
        FakeDB(),
        FakeExploreService(),
    )
    commands = _payload_commands(payload)
    assert commands == ["探险状态", "结束探险", "探险记录", "探险列表", "背包", "纳戒"]
    assert commands.count("探险状态") == 1
    assert len(commands) <= 6


def test_command_guide_buttons() -> None:
    """指南主入口只展示方向，具体业务入口下沉到方向页。"""

    message = markdown_message_from_text(help_service.command_guide())
    assert message is not None
    rows = message["keyboard"]["content"]["rows"]
    commands = [item["action"]["data"] for row in rows for item in row["buttons"]]
    assert commands == ["指南 成长", "指南 行囊", "指南 战斗", "指南 交易", "指南 世界"]

    battle_message = markdown_message_from_text(help_service.command_guide("战斗"))
    assert battle_message is not None
    battle_commands = [
        item["action"]["data"]
        for row in battle_message["keyboard"]["content"]["rows"]
        for item in row["buttons"]
    ]
    assert battle_commands[:4] == ["地图", "探险列表", "探险状态", "结束探险"]
    assert "首领" in battle_commands
    assert "虫洞奖励" in battle_commands
    assert battle_commands[-1] == "指南"

    trade_message = markdown_message_from_text(help_service.command_guide("交易"))
    assert trade_message is not None
    trade_commands = [
        item["action"]["data"]
        for row in trade_message["keyboard"]["content"]["rows"]
        for item in row["buttons"]
    ]
    assert "商场推荐" in trade_commands
    assert "自动出售" in trade_commands
    assert "出售全部 武器" in trade_commands


def _payload_commands(payload: dict) -> list[str]:
    """展开 markdown payload 里的按钮命令。"""

    rows = payload["message"]["keyboard"]["content"]["rows"]
    return [item["action"]["data"] for row in rows for item in row["buttons"]]


def main() -> None:
    test_button_default()
    test_keyboard_limit()
    test_plain_suggestion_uses_default_markdown_buttons()
    test_button_tags_to_markdown()
    test_button_tags_keep_command_text()
    test_reply_text_with_button_tags_to_markdown()
    test_reply_keeps_long_handwritten_business_buttons()
    test_reply_header_notice_line_is_second_line()
    test_reply_header_notice_keeps_handwritten_buttons()
    test_reply_header_notice_not_used_for_predictive_buttons()
    test_reply_header_notice_failure_is_silent()
    test_reply_header_notice_from_real_tables()
    test_hint_without_button_tags_uses_default_markdown_buttons()
    test_predictive_buttons_from_content()
    test_predictive_buttons_before_context_buttons()
    test_command_guide_buttons()
    print("修仙 markdown 按钮测试通过")


if __name__ == "__main__":
    main()
