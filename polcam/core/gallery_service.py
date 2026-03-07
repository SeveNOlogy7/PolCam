"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

图库数据服务
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional, Union

from qtpy import QtCore
import numpy as np

from .raw_image_service import RawImageService


@dataclass(slots=True)
class GalleryItem:
    id: int
    file_name: str
    file_path: str
    captured_at: float
    width: int
    height: int
    file_size: int
    file_format: str
    source: str
    metadata: Dict[str, Any]
    created_at: float

    @property
    def captured_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.captured_at)


class GalleryService:
    """管理自动保存图像及其数据库记录。"""

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        raw_image_service: Optional[RawImageService] = None,
    ):
        self._raw_image_service = raw_image_service or RawImageService()
        self._db_path = Path(db_path).expanduser() if db_path else self._build_default_db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _build_default_db_path(self) -> Path:
        return Path.home() / "PolCam" / "gallery.db"

    def _get_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self):
        with self._get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS gallery_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL UNIQUE,
                    captured_at REAL NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_format TEXT NOT NULL,
                    source TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_gallery_items_captured_at ON gallery_items(captured_at DESC)"
            )
            connection.commit()

    def save_capture(
        self,
        frame: np.ndarray,
        save_directory: Union[str, Path],
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        extension: str = RawImageService.DEFAULT_EXTENSION,
        source: str = "single_capture",
    ) -> GalleryItem:
        capture_time = float(timestamp if timestamp is not None else time.time())
        file_path = self._raw_image_service.build_auto_save_path(
            save_directory,
            timestamp=capture_time,
            suffix="_RAW",
            extension=extension,
        )
        saved_path = self._raw_image_service.save_image(frame, file_path)
        file_stat = saved_path.stat()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

        with self._get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO gallery_items (
                    file_name, file_path, captured_at, width, height,
                    file_size, file_format, source, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    saved_path.name,
                    str(saved_path),
                    capture_time,
                    int(frame.shape[1]),
                    int(frame.shape[0]),
                    int(file_stat.st_size),
                    saved_path.suffix.lower().lstrip("."),
                    source,
                    metadata_json,
                    time.time(),
                ),
            )
            connection.commit()
            if cursor.lastrowid is None:
                raise RuntimeError("创建图库记录失败")
            item_id = int(cursor.lastrowid)

        return self.get_item(item_id)

    def list_items(self) -> List[GalleryItem]:
        with self._get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, file_name, file_path, captured_at, width, height,
                       file_size, file_format, source, metadata_json, created_at
                FROM gallery_items
                ORDER BY captured_at DESC, id DESC
                """
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def get_item(self, item_id: int) -> GalleryItem:
        with self._get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, file_name, file_path, captured_at, width, height,
                       file_size, file_format, source, metadata_json, created_at
                FROM gallery_items
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"图库记录不存在: {item_id}")
        return self._row_to_item(row)

    def delete_item(self, item_id: int) -> GalleryItem:
        item = self.get_item(item_id)
        file_path = Path(item.file_path)
        if file_path.exists():
            file_path.unlink()

        with self._get_connection() as connection:
            connection.execute("DELETE FROM gallery_items WHERE id = ?", (item_id,))
            connection.commit()
        return item

    def delete_items(self, item_ids: List[int]) -> List[GalleryItem]:
        deleted_items: List[GalleryItem] = []
        for item_id in item_ids:
            deleted_items.append(self.delete_item(item_id))
        return deleted_items

    def _row_to_item(self, row: sqlite3.Row) -> GalleryItem:
        metadata_text = row["metadata_json"] or "{}"
        try:
            metadata = json.loads(metadata_text)
        except json.JSONDecodeError:
            metadata = {}

        return GalleryItem(
            id=int(row["id"]),
            file_name=str(row["file_name"]),
            file_path=str(row["file_path"]),
            captured_at=float(row["captured_at"]),
            width=int(row["width"]),
            height=int(row["height"]),
            file_size=int(row["file_size"]),
            file_format=str(row["file_format"]),
            source=str(row["source"]),
            metadata=metadata,
            created_at=float(row["created_at"]),
        )
