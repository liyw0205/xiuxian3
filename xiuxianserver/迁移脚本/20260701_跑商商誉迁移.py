#!/usr/bin/env python3
"""跑商商誉字段迁移。

用途：
1. 给 trade_records 增加商誉/散商拆分字段。
2. 将旧 sell 记录回填为商誉内成交，保留线上既有市场占用事实。
3. 将 schema_meta.version 升级到 2026070101。

脚本只依赖 Python 标准库，优先配合 xiuxianserver/start.sh 创建的 .venv 运行。
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


TARGET_VERSION = 2026070101
PREVIOUS_VERSION = 2026062901
INDEX_ENTRY_ERROR_RE = re.compile(r"wrong # of entries in index ([^\s]+)")


def _server_dir() -> Path:
    """返回 xiuxianserver 目录。

    迁移脚本固定放在 xiuxianserver/迁移脚本 下，父目录就是服务端根目录。
    线上用 bash 迁移脚本/start.sh 或 python 迁移脚本/xxx.py 执行时，都不需要依赖当前工作目录。
    """

    return Path(__file__).resolve().parents[1]


def _db_path(argv: list[str]) -> Path:
    if len(argv) >= 2:
        return Path(argv[1]).expanduser().resolve()
    env_path = os.environ.get("XIUXIAN_DB")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return (_server_dir() / "修仙" / "xiuxian.db").resolve()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table,),
    ).fetchone()
    return bool(row)


def _schema_version(conn: sqlite3.Connection) -> int | None:
    if not _table_exists(conn, "schema_meta"):
        return None
    row = conn.execute("SELECT value FROM schema_meta WHERE key = 'version'").fetchone()
    if not row:
        return None
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return None


def _backup(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.bak-{stamp}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def _ensure_columns(conn: sqlite3.Connection) -> list[str]:
    added: list[str] = []
    columns = _columns(conn, "trade_records")
    definitions = [
        ("effective_quantity", "INTEGER NOT NULL DEFAULT 0"),
        ("fatigue_quantity", "INTEGER NOT NULL DEFAULT 0"),
        ("effective_profit", "INTEGER NOT NULL DEFAULT 0"),
        ("fatigue_profit", "INTEGER NOT NULL DEFAULT 0"),
    ]
    for name, definition in definitions:
        if name in columns:
            continue
        conn.execute(f"ALTER TABLE trade_records ADD COLUMN {name} {definition}")
        added.append(name)
    return added


def _backfill_trade_records(conn: sqlite3.Connection) -> int:
    """回填旧普通跑商记录。

    旧库没有商誉/散商概念。迁移时把已有 sell 记录视为商誉成交，
    这样今日和近几天市场占用不会被清零；净利润用同玩家同业务日同商品
    的买入均价估算，成本缺失时按 0 处理，避免凭空抬高奖励。
    """

    conn.execute(
        """
        UPDATE trade_records
        SET effective_quantity = CASE WHEN action = 'sell' THEN quantity ELSE 0 END,
            fatigue_quantity = 0
        WHERE effective_quantity = 0
          AND fatigue_quantity = 0
          AND action IN ('buy', 'sell')
        """
    )
    cursor = conn.execute(
        """
        UPDATE trade_records AS sell
        SET effective_profit = MAX(
                0,
                (sell.total_price - sell.fee)
                - (
                    sell.effective_quantity * COALESCE(
                        (
                            SELECT CAST(ROUND(
                                SUM(buy.total_price + buy.fee) * 1.0 / NULLIF(SUM(buy.quantity), 0)
                            ) AS INTEGER)
                            FROM trade_records AS buy
                            WHERE buy.client_id = sell.client_id
                              AND buy.business_day = sell.business_day
                              AND buy.item_id = sell.item_id
                              AND buy.action = 'buy'
                        ),
                        sell.total_price / NULLIF(sell.quantity, 0),
                        0
                    )
                )
            ),
            fatigue_profit = 0
        WHERE sell.action = 'sell'
          AND sell.effective_quantity > 0
          AND sell.fatigue_quantity = 0
          AND sell.effective_profit = 0
          AND sell.fatigue_profit = 0
        """
    )
    conn.execute(
        """
        UPDATE trade_records
        SET effective_profit = 0,
            fatigue_profit = 0
        WHERE action != 'sell'
        """
    )
    return int(cursor.rowcount or 0)


def _set_version(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO schema_meta (key, value)
        VALUES ('version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(TARGET_VERSION),),
    )


def _integrity_errors(conn: sqlite3.Connection) -> list[str]:
    """返回 SQLite 完整性检查错误；没有错误时返回空列表。"""

    rows = conn.execute("PRAGMA integrity_check").fetchall()
    messages = [str(row[0]) for row in rows if row and row[0]]
    if messages == ["ok"]:
        return []
    return messages or ["unknown"]


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _repair_index_entry_errors(conn: sqlite3.Connection, errors: list[str]) -> list[str]:
    """修复完整性检查里明确指出的索引条目数量不一致问题。

    SQLite 偶尔会因为异常退出、旧进程残留或宿主机写入中断，留下表数据正常但索引条目
    数量不一致的库。这个问题可以通过 REINDEX 重建索引修复；如果完整性检查报的是其他
    类型错误，脚本会继续失败，避免把真正的数据损坏吞掉。
    """

    index_names = sorted(
        {
            match.group(1)
            for error in errors
            for match in INDEX_ENTRY_ERROR_RE.finditer(error)
        }
    )
    if not index_names:
        return []

    repaired: list[str] = []
    for index_name in index_names:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ? LIMIT 1",
            (index_name,),
        ).fetchone()
        if exists:
            conn.execute(f"REINDEX {_quote_identifier(index_name)}")
            repaired.append(index_name)

    return repaired


def main(argv: list[str]) -> int:
    db_path = _db_path(argv)
    if not db_path.exists():
        print(f"[trade-migration][error] 数据库不存在：{db_path}", file=sys.stderr)
        return 1

    backup_path = _backup(db_path)
    print(f"[trade-migration] 已备份：{backup_path}")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN")
        if not _table_exists(conn, "trade_records"):
            raise RuntimeError("缺少 trade_records 表，不能迁移。")
        current_version = _schema_version(conn)
        if current_version not in {None, PREVIOUS_VERSION, TARGET_VERSION}:
            print(f"[trade-migration] 当前版本 {current_version}，仍按实际表结构尝试幂等迁移。")
        added = _ensure_columns(conn)
        backfilled = _backfill_trade_records(conn)
        _set_version(conn)
        repaired_indexes: list[str] = []
        integrity_errors = _integrity_errors(conn)
        if integrity_errors:
            repaired_indexes = _repair_index_entry_errors(conn, integrity_errors)
            if repaired_indexes:
                integrity_errors = _integrity_errors(conn)
        if integrity_errors:
            raise RuntimeError(f"PRAGMA integrity_check 失败：{'；'.join(integrity_errors)}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[trade-migration] 补充字段：{', '.join(added) if added else '无，已存在'}")
    print(f"[trade-migration] 回填普通跑商 sell 记录：{backfilled} 条")
    if repaired_indexes:
        print(f"[trade-migration] 已重建索引：{', '.join(repaired_indexes)}")
    print(f"[trade-migration] schema_meta.version = {TARGET_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
