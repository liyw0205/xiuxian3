"""修仙长期记录表测试。

运行方式：

    python test/修仙_新表记录测试.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from 修仙.common import ts
from 修仙.constants import SCHEMA_VERSION
from 修仙.rules import weapon_exp_for_level
from 修仙.sql import XiuxianDB
from 修仙.玩家.service import PlayerService
from 修仙.武器.service import WeaponService
from 修仙.源库.service import SourceVaultService


def main() -> None:
    """验证新表不只是建表，也会沉淀真实数据。"""

    with TemporaryDirectory() as temp_dir:
        _assert_weapon_exp_migration(Path(temp_dir) / "xiuxian_migrate_test.db")

        db = XiuxianDB(Path(temp_dir) / "xiuxian_records_test.db")
        player = PlayerService(db)
        weapon = WeaponService(db)
        vault = SourceVaultService(db)

        assert "创建成功" in player.create("record_player", "青衫客")
        assert "签到成功" in player.sign("record_player")
        assert "新手礼包领取成功" in player.newbie_gift("record_player")
        assert "已存入源石" in vault.deposit("record_player", 1000)
        weapon.ensure_starter_weapon("record_player")
        weapon_id = db.fetch_one("SELECT weapon_id FROM player_weapons WHERE holder_id = ?", ("record_player",))
        assert weapon_id is not None
        weapon_id_int = int(weapon_id["weapon_id"])
        assert "升级成功" in weapon.upgrade("record_player", str(weapon_id_int))
        with db.transaction() as conn:
            weapon.record_weapon_combat_conn(
                conn,
                "record_player",
                weapon_id_int,
                monster_kill=True,
                damage=88,
                weapon_exp=321,
            )
        weapon_row = db.fetch_one("SELECT level, exp FROM player_weapons WHERE weapon_id = ?", (weapon_id_int,))
        assert weapon_row is not None
        assert int(weapon_row["level"]) == 2
        assert int(weapon_row["exp"]) == weapon_exp_for_level(1) + 321
        assert "经验:51/612" in weapon.list_weapons("record_player")

        with db.transaction() as conn:
            conn.execute(
                "UPDATE players SET level = 9, exp = 12345, source_stones = source_stones + 500000 WHERE client_id = ?",
                ("record_player",),
            )
            conn.execute(
                "UPDATE source_vaults SET balance = 120000 WHERE client_id = ?",
                ("record_player",),
            )
            for index in range(5):
                conn.execute(
                    """
                    INSERT INTO exploration_records
                    (client_id, location_name, status, started_at, ready_at, finished_at, result, claimed)
                    VALUES (?, ?, '已领取', ?, ?, ?, '{}', 1)
                    """,
                    ("record_player", "青岚坊", ts(), ts(), ts()),
                )
            for index in range(20):
                conn.execute(
                    """
                    INSERT INTO trade_records
                    (client_id, action, item_id, quantity, total_price, fee, location_name, business_day, created_at)
                    VALUES (?, 'sell', ?, 1, 10000, 100, '天枢城', '2099-01-01', ?)
                    """,
                    ("record_player", f"test_trade_{index}", ts()),
                )

        profile_text = player.profile("record_player")
        assert "经验" in profile_text
        assert "源石" in profile_text
        assert "武器" in profile_text
        assert "修仙日记" in player.diary("record_player")

        journal_count = db.fetch_one(
            "SELECT COUNT(*) AS count FROM player_journals WHERE client_id = ?",
            ("record_player",),
        )
        assert int(journal_count["count"]) >= 8
        level_journal = db.fetch_one(
            """
            SELECT text FROM player_journals
            WHERE client_id = ? AND milestone_key = 'level'
            """,
            ("record_player",),
        )
        assert level_journal and "累计经验 12345" in level_journal["text"]

        title_count = db.fetch_one(
            "SELECT COUNT(*) AS count FROM player_titles WHERE client_id = ?",
            ("record_player",),
        )
        active_title = db.fetch_one(
            "SELECT title FROM player_titles WHERE client_id = ? AND active = 1",
            ("record_player",),
        )
        assert int(title_count["count"]) >= 5
        assert active_title is not None

        log_actions = {
            row["action"]
            for row in db.fetch_all(
                "SELECT action FROM game_logs WHERE client_id = ?",
                ("record_player",),
            )
        }
        assert {"创建用户", "签到", "新手礼包", "存入源石", "升级武器"}.issubset(log_actions)
        db.close()

    print("修仙长期记录表测试通过")


def _assert_weapon_exp_migration(db_path: Path) -> None:
    """旧版武器表迁移时只补经验字段，不重建整库。"""

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO schema_meta (key, value) VALUES ('version', '2026060302');
        CREATE TABLE player_weapons (
            weapon_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT NOT NULL,
            weapon_def_id TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 0,
            max_level INTEGER NOT NULL,
            quality TEXT NOT NULL,
            enchant_effects TEXT NOT NULL DEFAULT '[]',
            equipped INTEGER NOT NULL DEFAULT 0,
            custom_name TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE players (
            client_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            exp INTEGER NOT NULL DEFAULT 0,
            hp INTEGER NOT NULL DEFAULT 100,
            max_hp INTEGER NOT NULL DEFAULT 100,
            mp INTEGER NOT NULL DEFAULT 60,
            max_mp INTEGER NOT NULL DEFAULT 60,
            physique_id TEXT NOT NULL DEFAULT 'fanti',
            physique INTEGER NOT NULL DEFAULT 0,
            base_attack INTEGER NOT NULL DEFAULT 5,
            defense INTEGER NOT NULL DEFAULT 0,
            source_stones INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT '空闲',
            rest_full_at TEXT,
            location_name TEXT NOT NULL DEFAULT '天枢城',
            x INTEGER NOT NULL DEFAULT 0,
            y INTEGER NOT NULL DEFAULT 0,
            backpack_limit INTEGER NOT NULL DEFAULT 80,
            weight_limit INTEGER NOT NULL DEFAULT 500,
            auto_use_medicine INTEGER NOT NULL DEFAULT 1,
            battle_log_detail INTEGER NOT NULL DEFAULT 0,
            last_sign_date TEXT,
            newbie_claimed INTEGER NOT NULL DEFAULT 0,
            last_rename_at TEXT,
            created_at TEXT NOT NULL
        );
        INSERT INTO player_weapons
        (owner_id, weapon_def_id, level, max_level, quality, equipped, enchant_effects, custom_name, created_at)
        VALUES ('migrate_player', 'qinglan_duanjian', 3, 40, '凡品', 1, '[]', '', '2099-01-01 00:00:00');
        """
    )
    conn.commit()
    conn.close()

    db = XiuxianDB(db_path)
    db.init()
    columns = {row["name"] for row in db.fetch_all("PRAGMA table_info(player_weapons)")}
    assert "exp" in columns
    player_columns = {row["name"] for row in db.fetch_all("PRAGMA table_info(players)")}
    assert {"rest_window_started_at", "rest_window_hp", "rest_window_mp", "rest_window_elapsed_seconds"}.issubset(player_columns)
    weapon_row = db.fetch_one("SELECT level, exp FROM player_weapons WHERE holder_id = ?", ("migrate_player",))
    assert weapon_row is not None
    assert int(weapon_row["level"]) == 3
    assert int(weapon_row["exp"]) == weapon_exp_for_level(3)
    version_row = db.fetch_one("SELECT value FROM schema_meta WHERE key = 'version'")
    assert version_row is not None
    assert int(version_row["value"]) == SCHEMA_VERSION
    db.close()


if __name__ == "__main__":
    main()
