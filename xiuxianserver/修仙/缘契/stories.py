"""缘契剧本发现和读取。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


STORIES_DIR = Path(__file__).resolve().parent / "stories"
STORY_FILE_NAME = "story-data.json"
STORY_KEY_RE = re.compile(r"[^A-Za-z0-9_-]+")


@dataclass(frozen=True)
class YuanqiStory:
    """一个可被缘契随机抽到的文游剧本。"""

    key: str
    title: str
    subtitle: str
    path: Path


def discover_stories() -> list[YuanqiStory]:
    """遍历本组件内已启用的剧本文件。"""

    if not STORIES_DIR.exists():
        return []

    stories: list[YuanqiStory] = []
    for path in sorted(STORIES_DIR.glob(f"*/{STORY_FILE_NAME}"), key=lambda item: item.parent.name):
        key = safe_story_key(path.parent.name)
        if not key:
            continue
        data = _read_story_json(path)
        game = data.get("game") if isinstance(data.get("game"), dict) else {}
        title = str(game.get("title") or key).strip()
        subtitle = str(game.get("subtitle") or "").strip()
        stories.append(YuanqiStory(key=key, title=title, subtitle=subtitle, path=path))
    return stories


def find_story(value: str, stories: list[YuanqiStory] | None = None) -> YuanqiStory | None:
    """按目录 key 或展示标题查找剧本。"""

    target = _normalize_story_lookup(value)
    if not target:
        return None

    candidates = stories if stories is not None else discover_stories()
    for story in candidates:
        if target in {
            _normalize_story_lookup(story.key),
            _normalize_story_lookup(story.title),
        }:
            return story
    return None


def load_story(story: YuanqiStory) -> dict[str, Any]:
    """读取某个剧本数据。"""

    return _read_story_json(story.path)


def safe_story_key(value: str) -> str:
    """把目录名收敛为稳定剧本键。"""

    return STORY_KEY_RE.sub("", str(value or "").strip())[:64]


def _normalize_story_lookup(value: str) -> str:
    """收敛用户输入的剧本名，支持中文标题和目录 key。"""

    return re.sub(r"\s+", "", str(value or "").strip()).lower()


def _read_story_json(path: Path) -> dict[str, Any]:
    """读取剧本 JSON；不是对象时视为配置错误。"""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"缘契剧本无法读取：{path.name}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"缘契剧本不是 JSON 对象：{path.name}")
    return data
