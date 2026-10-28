# -*- coding: utf-8 -*-
"""TaskStore 隐藏标记测试：删除任务持久化（刷新/新建任务不复活）。"""
from app.core.task_store import TaskStore


def test_hide_task_persists_across_refresh(tmp_path):
    store = TaskStore(tmp_path / "ws")
    d1 = store.create("US", 20)
    d2 = store.create("DE", 5)
    assert len(store.list_tasks()) == 2

    store.hide_task(d1.name)
    # 模拟刷新/新建任务后重新扫描目录：隐藏的不再出现
    store2 = TaskStore(tmp_path / "ws")
    visible = [t["dir"] for t in store2.list_tasks()]
    assert d2.name in visible
    assert d1.name not in visible


def test_unhide_restores(tmp_path):
    store = TaskStore(tmp_path / "ws")
    d1 = store.create("US", 20)
    store.hide_task(d1.name)
    assert d1.name not in [t["dir"] for t in store.list_tasks()]
    store.unhide_task(d1.name)
    assert d1.name in [t["dir"] for t in store.list_tasks()]


def test_hide_nonexistent_and_duplicate_safe(tmp_path):
    store = TaskStore(tmp_path / "ws")
    d1 = store.create("US", 20)
    store.hide_task(d1.name)
    store.hide_task(d1.name)  # 重复隐藏不产生重复条目
    assert store.hidden_tasks().count(d1.name) == 1


def test_list_tasks_marks_hidden(tmp_path):
    store = TaskStore(tmp_path / "ws")
    d1 = store.create("US", 20)
    store.hide_task(d1.name)
    d2 = store.create("DE", 5)
    all_tasks = store.list_tasks(exclude_hidden=False)
    by_dir = {t["dir"]: t for t in all_tasks}
    assert by_dir[d1.name]["hidden"] is True
    assert by_dir[d2.name]["hidden"] is False


# ---------- Phase 2：任务自定义命名（display_name 仅列表显示） ----------

def test_create_with_display_name(tmp_path):
    store = TaskStore(tmp_path / "ws")
    d = store.create("US", 20, display_name="泳装 2026 旺季")
    state = store.read_state(d)
    assert state["display_name"] == "泳装 2026 旺季"
    assert d.name not in ("泳装 2026 旺季",)  # 目录名保持自动格式
    tasks = store.list_tasks()
    assert tasks[0]["display_name"] == "泳装 2026 旺季"
    assert tasks[0]["dir"] == d.name


def test_display_name_defaults_to_dir(tmp_path):
    """旧任务/未命名任务：显示名回退目录名（零迁移）。"""
    store = TaskStore(tmp_path / "ws")
    d = store.create("US", 5)
    tasks = store.list_tasks()
    assert tasks[0]["display_name"] == d.name
    assert store.display_name(d) == d.name


def test_rename_and_clear_display_name(tmp_path):
    store = TaskStore(tmp_path / "ws")
    d = store.create("US", 5, display_name="A")
    store.set_display_name(d, "B")
    assert store.display_name(d) == "B"
    store.set_display_name(d, "")  # 清空恢复自动名
    assert store.display_name(d) == d.name
    state = store.read_state(d)
    assert "display_name" not in state


def test_rename_persists_across_store_instances(tmp_path):
    store = TaskStore(tmp_path / "ws")
    d = store.create("US", 5)
    store.set_display_name(d, "重命名后")
    store2 = TaskStore(tmp_path / "ws")  # 模拟重启
    assert store2.display_name(d) == "重命名后"
    assert store2.list_tasks()[0]["display_name"] == "重命名后"
