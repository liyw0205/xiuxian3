"""修仙 markdown 按钮协议测试。"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.修仙.common import hint
from src.修仙.markdown_utils import MarkdownKeyboard, button, markdown_message_from_text
from src.修仙.玩家.service import service as player_service
from src.修仙.reply import _with_player_name


class FakeDB:
    """只给回复包装读取玩家名。"""

    def fetch_one(self, *_args, **_kwargs) -> dict:
        return {"display_name": "青衫客"}


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


def test_plain_suggestion_stays_text() -> None:
    """没有 `<命令>` 时，普通建议文本不再自动转按钮。"""

    message = markdown_message_from_text("血气不足。\n发送：休息，时间到后发送：修仙信息")
    assert message is None

    payload = _with_player_name(
        "player_ws",
        {"code": 202, "type": "text", "message": "血气不足。\n发送：休息，时间到后发送：修仙信息"},
        FakeDB(),
    )
    assert payload["type"] == "text"
    assert payload["message"].endswith("发送：休息，时间到后发送：修仙信息")


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
    assert "【青衫客】" in payload["message"]["content"]
    assert "<探险状态>" not in payload["message"]["content"]
    rows = payload["message"]["keyboard"]["content"]["rows"]
    assert [item["action"]["data"] for item in rows[0]["buttons"]] == ["探险状态", "结束探险"]


def test_hint_stays_text_without_button_tags() -> None:
    """hint 只负责拼接建议；没有 `<命令>` 就保持 text。"""

    text = hint("血气不足。", "发送：休息，时间到后发送：结束休息")
    assert text == "血气不足。\n发送：休息，时间到后发送：结束休息"

    payload = _with_player_name(
        "player_ws",
        {"code": 202, "type": "text", "message": text},
        FakeDB(),
    )
    assert payload["type"] == "text"
    assert payload["message"].endswith("发送：休息，时间到后发送：结束休息")


def test_player_command_guide_buttons() -> None:
    """玩家指南里的手写按钮都能转成 markdown。"""

    message = markdown_message_from_text(player_service.command_guide())
    assert message is not None
    rows = message["keyboard"]["content"]["rows"]
    commands = [item["action"]["data"] for row in rows for item in row["buttons"]]
    assert commands[:3] == ["修仙信息", "背包", "纳戒"]
    assert "探险状态" in commands
    assert "结束探险" in commands
    assert "宝石" in commands
    assert "武器" in commands
    assert commands[-1] == "修仙早报"


def main() -> None:
    test_button_default()
    test_keyboard_limit()
    test_plain_suggestion_stays_text()
    test_button_tags_to_markdown()
    test_button_tags_keep_command_text()
    test_reply_text_with_button_tags_to_markdown()
    test_hint_stays_text_without_button_tags()
    test_player_command_guide_buttons()
    print("修仙 markdown 按钮测试通过")


if __name__ == "__main__":
    main()
