# -*- coding: utf-8 -*-
"""任务目录与状态管理：任务创建、状态机、断点续跑基础。"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

PHASES = [
    "created",        # 已创建
    "collecting",     # 采集（node/反查/矩阵）
    "aggregating",    # 本地聚合脚本
    "labeling",       # LLM 翻译分类
    "trends",         # 趋势
    "analyzing",      # LLM 分析
    "building",       # Excel 生成
    "validating",     # 报告验收
    "done",           # 完成
    "failed",         # 失败
    "canceled",       # 已取消
]


def safe_task_id() -> str:
    return uuid.uuid4().hex[:8]


def task_dir_name(marketplace: str, asin_count: int, task_id: str,
                  when: str | None = None) -> str:
    when = when or time.strftime("%Y%m%d-%H%M%S")
    return f"{when}_{marketplace}_{asin_count}ASIN_{task_id}"


class TaskStore:
    """管理 tasks/ 下任务目录的创建、隐藏标记与 task.json 状态。"""

    def __init__(self, workspace_dir: str | Path) -> None:
        self.workspace = Path(workspace_dir)
        self.tasks_dir = self.workspace / "tasks"
        self.hidden_path = self.workspace / "hidden_tasks.json"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    # ---------- 隐藏标记（持久化“仅移出列表”，防刷新复活）----------

    def _load_hidden(self) -> list[str]:
        if not self.hidden_path.exists():
            return []
        try:
            data = json.loads(self.hidden_path.read_text(encoding="utf-8"))
            return data.get("hidden", []) if isinstance(data, dict) else []
        except Exception:
            return []

    def _save_hidden(self, names: list[str]) -> None:
        self.hidden_path.write_text(
            json.dumps({"hidden": names}, ensure_ascii=False, indent=2),
            encoding="utf-8")

    def hide_task(self, dir_name: str) -> None:
        """把任务从列表隐藏（保留数据目录，可从 hidden_tasks.json 恢复）。"""
        hidden = [n for n in self._load_hidden() if n != dir_name]
        hidden.append(dir_name)
        self._save_hidden(hidden)

    def unhide_task(self, dir_name: str) -> None:
        hidden = [n for n in self._load_hidden() if n != dir_name]
        self._save_hidden(hidden)

    def hidden_tasks(self) -> list[str]:
        return self._load_hidden()

    def create(self, marketplace: str, asin_count: int,
               display_name: str | None = None) -> Path:
        """创建一个任务目录，返回其路径。display_name 可选（仅列表显示名）。"""
        task_id = safe_task_id()
        name = task_dir_name(marketplace, asin_count, task_id)
        task_dir = self.tasks_dir / name
        task_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("raw", "cache", "logs", "output"):
            (task_dir / sub).mkdir(exist_ok=True)
        state = {
            "task_id": task_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "phase": "created",
            "message": "任务已创建",
        }
        if display_name:
            state["display_name"] = display_name
        self.write_state(task_dir, state)
        return task_dir

    def set_display_name(self, task_dir: Path, display_name: str) -> None:
        """设置/更新任务的列表显示名（只改 task.json，不动目录名/Excel 名）。"""
        state = self.read_state(task_dir)
        name = display_name.strip()
        if name:
            state["display_name"] = name
        else:
            state.pop("display_name", None)  # 清空回退自动名
        state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self.write_state(task_dir, state)

    def display_name(self, task_dir: Path) -> str:
        """返回任务的列表显示名；无 display_name 时返回目录名（旧任务零迁移）。"""
        state = self.read_state(task_dir)
        return state.get("display_name") or task_dir.name

    # ---------- 状态 ----------

    def state_path(self, task_dir: Path) -> Path:
        return Path(task_dir) / "task.json"

    def read_state(self, task_dir: Path) -> dict:
        p = self.state_path(task_dir)
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def write_state(self, task_dir: Path, state: dict) -> None:
        p = self.state_path(task_dir)
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def set_phase(self, task_dir: Path, phase: str, message: str = "") -> None:
        if phase not in PHASES:
            raise ValueError(f"未知阶段: {phase}")
        state = self.read_state(task_dir)
        state["phase"] = phase
        state["message"] = message
        state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self.write_state(task_dir, state)

    def log(self, task_dir: Path, line: str) -> None:
        log_dir = Path(task_dir) / "logs"
        log_dir.mkdir(exist_ok=True)
        path = log_dir / "run.log"
        ts = time.strftime("%H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {line}\n")

    # ---------- 任务列表 ----------

    def list_tasks(self, exclude_hidden: bool = True) -> list[dict]:
        out = []
        hidden = set(self._load_hidden())
        for d in sorted(self.tasks_dir.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            if exclude_hidden and d.name in hidden:
                continue
            state = self.read_state(d)
            m = re.match(r"(\d{8}-\d{6})_([A-Z]{2})_(\d+)ASIN_([0-9a-f]{8})", d.name)
            out.append({
                "dir": d.name,
                "path": str(d),
                "display_name": state.get("display_name", d.name),
                "created": m.group(1) if m else state.get("created_at", ""),
                "marketplace": m.group(2) if m else "",
                "asin_count": int(m.group(3)) if m else 0,
                "task_id": m.group(4) if m else "",
                "phase": state.get("phase", "unknown"),
                "message": state.get("message", ""),
                "hidden": d.name in hidden,
            })
        return out
