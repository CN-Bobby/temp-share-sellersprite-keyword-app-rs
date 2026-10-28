# -*- coding: utf-8 -*-
"""任务列表页：任务状态、日志面板、开始/继续、取消、打开目录。

线程模型（规避 codex 版 GUI 多线程 bug）：pipeline 跑在 QThread，
事件经线程安全队列 + QTimer 轮询转发到 GUI 线程，杜绝跨线程直接操作控件。
"""
from __future__ import annotations

import os
import queue
from pathlib import Path

from PySide6.QtCore import QThread, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                               QMessageBox, QPlainTextEdit, QPushButton,
                               QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from app.core.config import Settings
from app.core.pipeline import Pipeline
from app.core.task_store import TaskStore


class PipelineWorker(QThread):
    """后台执行线程：pipeline 事件全部进队列，由 GUI QTimer 消费。"""

    def __init__(self, settings: Settings, task_dir: Path, store: TaskStore) -> None:
        super().__init__()
        self.queue: queue.Queue = queue.Queue()
        self.pipeline = Pipeline(settings, task_dir, store,
                                 on_event=self.queue.put)
        self.task_dir = task_dir

    def run(self) -> None:
        try:
            self.pipeline.run()
            self.queue.put({"kind": "worker_done"})
        except Exception as exc:  # noqa: BLE001
            self.queue.put({"kind": "worker_error", "error": str(exc)})

    def cancel(self) -> None:
        self.pipeline.cancel()


class TasksPage(QWidget):
    def __init__(self, settings: Settings, store: TaskStore,
                 settings_page=None) -> None:
        super().__init__()
        self.settings = settings
        self.store = store
        self.settings_page = settings_page  # 用于"开始执行"时自动登记输入框凭据
        self.worker: PipelineWorker | None = None
        self.current_task: str | None = None
        # Phase 3 队列状态（GUI 会话内）
        self.queue: list[str] = []
        self.queue_index: int = -1
        self.queue_results: dict[str, str] = {}

        lay = QVBoxLayout(self)
        splitter = QSplitter()

        # 左侧任务列表
        left = QWidget()
        ll = QVBoxLayout(left)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["任务名称", "站点", "ASIN数", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)  # 支持批量删除
        self.table.itemSelectionChanged.connect(self._on_select)
        self.table.itemDoubleClicked.connect(self._on_double_click)  # 双击重命名
        ll.addWidget(self.table)
        row = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.clicked.connect(self.refresh)
        self.select_all_btn = QPushButton("全选/取消")
        self.select_all_btn.clicked.connect(self._toggle_select_all)
        self.queue_btn = QPushButton("一键排队执行")
        self.queue_btn.clicked.connect(self._start_queue)
        self.queue_stop_btn = QPushButton("停止队列")
        self.queue_stop_btn.clicked.connect(self._stop_queue)
        self.queue_stop_btn.setEnabled(False)
        self.open_btn = QPushButton("打开任务目录")
        self.open_btn.clicked.connect(self._open_dir)
        self.del_btn = QPushButton("删除任务")
        self.del_btn.clicked.connect(self._delete_task)
        for b in (self.refresh_btn, self.select_all_btn, self.queue_btn,
                  self.queue_stop_btn, self.open_btn, self.del_btn):
            row.addWidget(b)
        row.addStretch(1)
        ll.addLayout(row)
        splitter.addWidget(left)

        # 右侧日志与状态
        right = QWidget()
        rl = QVBoxLayout(right)
        self.status_label = QLabel("未选择任务")
        self.status_label.setWordWrap(True)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        rl.addWidget(self.status_label)
        rl.addWidget(self.log_view, 1)
        ctrl = QHBoxLayout()
        self.start_btn = QPushButton("开始 / 继续执行")
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("取消任务")
        self.cancel_btn.clicked.connect(self._cancel)
        self.cancel_btn.setEnabled(False)
        ctrl.addWidget(self.start_btn)
        ctrl.addWidget(self.cancel_btn)
        ctrl.addStretch(1)
        rl.addLayout(ctrl)
        splitter.addWidget(right)
        splitter.setSizes([520, 520])
        lay.addWidget(splitter)

        # 事件轮询
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._drain_events)
        self.timer.start(120)

        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self._refresh_state)
        self.state_timer.start(2000)

    # ---------- 任务列表 ----------

    def refresh(self) -> None:
        tasks = self.store.list_tasks()
        self.table.setRowCount(len(tasks))
        for i, t in enumerate(tasks):
            name_item = QTableWidgetItem(str(t.get("display_name") or t["dir"]))
            name_item.setData(0x0100, t["dir"])  # Qt.UserRole：真实目录名
            name_item.setToolTip(f"{t['dir']}\n双击可重命名")
            self.table.setItem(i, 0, name_item)
            for col, key in enumerate(("marketplace", "asin_count", "phase"), start=1):
                item = QTableWidgetItem(str(t.get(key, "")))
                item.setData(0x0100, t["dir"])
                if col == 3:
                    # 状态徽章着色（Phase 4；仅样式不改变逻辑）
                    from app.gui.theme import phase_color

                    item.setForeground(QColor(phase_color(t.get("phase", ""))))
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                self.table.setItem(i, col, item)
        if tasks and self.current_task is None:
            self.table.selectRow(0)

    def _selected_dir(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return item.data(0x0100) if item else None

    def _selected_dirs(self) -> list[str]:
        """返回当前选中（可多选）的任务目录名列表。"""
        names = []
        for row in self.table.selectionModel().selectedRows():
            item = self.table.item(row.row(), 0)
            if item is not None:
                names.append(item.data(0x0100))
        return names

    def _on_select(self) -> None:
        name = self._selected_dir()
        self.current_task = name
        self._reload_log()

    def _reload_log(self) -> None:
        if not self.current_task:
            self.status_label.setText("未选择任务")
            self.log_view.clear()
            return
        state = self.store.read_state(self.store.tasks_dir / self.current_task)
        self.status_label.setText(
            f"状态：{state.get('phase', 'unknown')} — {state.get('message', '')}")
        log_path = self.store.tasks_dir / self.current_task / "logs" / "run.log"
        if log_path.exists():
            self.log_view.setPlainText(log_path.read_text(encoding="utf-8", errors="replace")[-30000:])
        else:
            self.log_view.setPlainText("（暂无日志）")
        self.cancel_btn.setEnabled(self.worker is not None and self.worker.isRunning())

    def _refresh_state(self) -> None:
        if self.current_task and self.worker is None:
            self._reload_log()

    def _on_double_click(self, item) -> None:
        """双击任务名称列 → 重命名（仅改 task.json 的 display_name）。"""
        if item.column() != 0:
            return
        name = item.data(0x0100)
        if not name:
            return
        current = self.store.display_name(self.store.tasks_dir / name)
        text, ok = QInputDialog.getText(
            self, "重命名任务",
            "任务名称（仅列表显示，不影响目录名与 Excel 文件名）：\n留空则恢复自动名。",
            text=current if current != name else "")
        if not ok:
            return
        self.store.set_display_name(self.store.tasks_dir / name, text.strip())
        self.refresh()

    # ---------- 控制 ----------

    def _start(self) -> None:
        if not self.current_task:
            QMessageBox.information(self, "提示", "请先选择任务")
            return
        if self.worker is not None and self.worker.isRunning():
            return
        if self.queue_index >= 0:
            QMessageBox.information(self, "队列运行中", "队列执行期间请使用“停止队列”或等待完成")
            return
        self._launch_task(self.current_task)

    def _launch_task(self, name: str) -> bool:
        """启动单个任务（手动与队列共用）。返回是否成功启动。"""
        task_dir = self.store.tasks_dir / name
        if not (task_dir / "input.json").exists():
            QMessageBox.warning(self, "任务不完整", f"{name}\n该任务缺少 input.json，无法执行")
            return False
        # 防呆：设置页输入框已填但未保存/测试时，开始执行前自动登记凭据
        self._maybe_autosave_credentials()
        if not self.settings.has_mcp_credentials():
            QMessageBox.warning(self, "缺少凭据",
                                "请先在“设置”页填写并保存 SellerSprite Secret Key\n（填写后点“测试连接”通过即自动登记）")
            return False
        if not self.settings.has_llm_credentials():
            QMessageBox.warning(self, "缺少凭据",
                                "请先在“设置”页填写并保存模型 API 凭据\n（填写后点“测试模型”通过即自动登记）")
            return False
        self.store.log(task_dir, "用户点击开始执行")
        self.worker = PipelineWorker(self.settings, task_dir, self.store)
        self.worker.finished.connect(lambda: self._on_worker_finished())
        self.worker.start()
        self.cancel_btn.setEnabled(True)
        self.start_btn.setEnabled(False)
        self.status_label.setText("执行中…")
        return True

    # ---------- Phase 3 批量排队 ----------

    def _toggle_select_all(self) -> None:
        sm = self.table.selectionModel()
        if sm is None or self.table.rowCount() == 0:
            return
        all_selected = len(sm.selectedRows()) == self.table.rowCount()
        if all_selected:
            sm.clearSelection()
            return
        from PySide6.QtCore import QItemSelectionModel

        for r in range(self.table.rowCount()):
            idx = self.table.model().index(r, 0)
            sm.select(idx, QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def _start_queue(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "队列运行中", "请先停止当前队列")
            return
        names = self._selected_dirs()
        if not names:
            QMessageBox.information(self, "提示", "请先选择任务（可多选或“全选”）")
            return
        # 只排队未完成任务（done 跳过；created/failed/canceled 均入队）
        pending = []
        for name in names:
            state = self.store.read_state(self.store.tasks_dir / name)
            if state.get("phase") != "done":
                pending.append(name)
        if not pending:
            QMessageBox.information(self, "提示", "所选任务均已完成，无需执行")
            return
        self.queue = pending
        self.queue_index = 0
        self.queue_results = {n: "queued" for n in pending}
        self.queue_btn.setEnabled(False)
        self.queue_stop_btn.setEnabled(True)
        self._run_next()

    def _run_next(self) -> None:
        if self.queue_index >= len(self.queue):
            self._finish_queue()
            return
        name = self.queue[self.queue_index]
        self.queue_results[name] = "running"
        self.current_task = name
        disp = self.store.display_name(self.store.tasks_dir / name)
        self.status_label.setText(
            f"队列 {self.queue_index + 1}/{len(self.queue)}：正在执行 {disp}")
        self._reload_log()
        if not self._launch_task(name):
            # 启动失败（缺凭据/任务不完整）→ 标记失败，跳过继续
            self.queue_results[name] = "failed"
            self._advance_queue()

    def _advance_queue(self) -> None:
        self.queue_index += 1
        self._run_next()

    def _stop_queue(self) -> None:
        """停止队列：取消当前任务，剩余标记 skipped（当前结束后即汇总，不再推进）。"""
        for i in range(self.queue_index, len(self.queue)):
            name = self.queue[i]
            if self.queue_results.get(name) not in ("done", "failed"):
                self.queue_results[name] = "skipped"
        self.queue_index = len(self.queue)  # 当前任务结束后直接 _finish_queue
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
        self.status_label.setText("正在停止队列…（等待当前任务结束）")

    def _finish_queue(self) -> None:
        done = sum(1 for v in self.queue_results.values() if v == "done")
        failed = sum(1 for v in self.queue_results.values() if v == "failed")
        skipped = sum(1 for v in self.queue_results.values() if v == "skipped")
        self.status_label.setText(
            f"队列完成：成功 {done} / 失败 {failed}"
            + (f" / 跳过 {skipped}" if skipped else ""))
        self.queue = []
        self.queue_index = -1
        self.queue_results = {}
        self.queue_btn.setEnabled(True)
        self.queue_stop_btn.setEnabled(False)
        self.refresh()
        QMessageBox.information(
            self, "队列执行完成",
            f"成功 {done} / 失败 {failed}" + (f" / 跳过 {skipped}" if skipped else ""))

    def _maybe_autosave_credentials(self) -> None:
        """把设置页输入框已填写的凭据（未保存时）就位登记到 settings/凭据管理器。

        仅在输入框存在值且凭据管理器缺失时写入，避免空值覆盖已保存密钥。
        """
        if self.settings_page is None:
            return
        sp = self.settings_page
        mcp_key = sp.mcp_key_edit.text().strip()
        if not self.settings.has_mcp_credentials() and mcp_key:
            self.settings.mcp_secret_key = mcp_key
            self.settings.mcp_url = sp.mcp_url_edit.text().strip()
        llm_key = sp.llm_key_edit.text().strip()
        llm_base = sp.llm_url_edit.text().strip()
        llm_model = sp.llm_model_edit.text().strip()
        if (not self.settings.has_llm_credentials()
                and llm_key and llm_base and llm_model):
            self.settings.llm_base_url = llm_base
            self.settings.llm_api_key = llm_key
            self.settings.llm_model = llm_model
        self.settings.save()

    def _cancel(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText("正在取消…（等待当前调用结束）")

    def _on_worker_finished(self) -> None:
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._reload_log()
        self.refresh()
        # 队列模式：标记结果并自动推进下一个（失败跳过，不中断队列）
        if self.queue_index >= 0 and self.current_task:
            name = self.current_task
            state = self.store.read_state(self.store.tasks_dir / name)
            phase = state.get("phase")
            if phase == "done":
                self.queue_results[name] = "done"
            elif phase == "canceled":
                self.queue_results[name] = "skipped"
            else:
                self.queue_results[name] = "failed"  # 失败写 message 后跳过
            self._advance_queue()

    # ---------- 事件消费 ----------

    def _drain_events(self) -> None:
        if self.worker is None:
            return
        changed = False
        while True:
            try:
                ev = self.worker.queue.get_nowait()
            except queue.Empty:
                break
            kind = ev.get("kind")
            if kind == "log":
                self.log_view.appendPlainText(ev.get("line", ""))
            elif kind == "phase":
                self.status_label.setText(f"状态：{ev.get('phase')} — {ev.get('message', '')}")
                changed = True
            elif kind == "rate_limit_wait":
                self.status_label.setText(
                    f"限流等待中… {ev.get('wait_seconds', 0):.0f} 秒后继续（{ev.get('tool')}）")
            elif kind == "worker_done":
                self.status_label.setText("任务完成")
                changed = True
            elif kind == "worker_error":
                self.status_label.setText(f"任务失败：{ev.get('error', '')[:200]}")
                changed = True
        if changed:
            self.refresh()

    # ---------- 其他 ----------

    def _open_dir(self) -> None:
        if self.current_task:
            os.startfile(str(self.store.tasks_dir / self.current_task))  # noqa: S606

    def _delete_task(self) -> None:
        """批量删除：持久隐藏（列表不再显示、数据保留）或移入回收站（真删）。"""
        names = self._selected_dirs()
        if not names:
            QMessageBox.information(self, "提示", "请先选择要删除的任务（可多选）")
            return
        n = len(names)
        box = QMessageBox(self)
        box.setWindowTitle("批量删除任务")
        box.setText(f"已选择 {n} 个任务。\n"
                    "“仅隐藏”只从列表移除（数据保留，刷新/新建任务不会再出现）；\n"
                    "“移入回收站”会把任务目录移入 Windows 回收站（数据可恢复）。")
        hide_btn = box.addButton(f"仅隐藏（{n} 个）", QMessageBox.AcceptRole)
        trash_btn = box.addButton(f"移入回收站（{n} 个）", QMessageBox.DestructiveRole)
        box.addButton("取消", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == hide_btn:
            for name in names:
                self.store.hide_task(name)  # 持久化隐藏标记，刷新/新建任务不再复活
            self.refresh()
        elif clicked == trash_btn:
            from send2trash import send2trash

            failed = []
            for name in names:
                try:
                    send2trash(str(self.store.tasks_dir / name))
                except Exception as exc:  # noqa: BLE001
                    failed.append(f"{name}: {exc}")
            if failed:
                QMessageBox.warning(self, "部分删除失败", "\n".join(failed)[:600])
            self.refresh()
