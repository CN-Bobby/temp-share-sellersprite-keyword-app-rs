# -*- coding: utf-8 -*-
"""新建任务页：多站点组（每组一个站点 ≤20 ASIN）、快照月份、预算核算与确认。"""
from __future__ import annotations

import json
import time
from typing import Callable

from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from app.core.config import Settings
from app.core.input_validator import MARKETPLACES, ValidationError, validate_task
from app.core.pipeline import build_plan, prepare_task_input
from app.core.task_store import TaskStore

CONFIRM_THRESHOLD = 30


class TaskCreatePage(QWidget):
    def __init__(self, settings: Settings, store: TaskStore,
                 on_created: Callable[[], None]) -> None:
        super().__init__()
        self.settings = settings
        self.store = store
        self.on_created = on_created

        lay = QVBoxLayout(self)

        # 站点组表格
        tip = QLabel("每个站点组一个站点、去重后 ≤20 个 ASIN；多站点调研请添加多个站点组。"
                     "支持 Node ID（每行可填，选填）。")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["站点", "ASIN（逗号/换行分隔）", "Node ID（选填）", ""])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table, 1)

        row = QHBoxLayout()
        self.add_group_btn = QPushButton("＋ 添加站点组")
        self.add_group_btn.clicked.connect(lambda: self._add_group())
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("任务名称（选填，仅列表显示）")
        self.name_edit.setFixedWidth(240)
        self.month_edit = QLineEdit()
        self.month_edit.setPlaceholderText("汇总月份 yyyyMM（留空=近30天）")
        self.month_edit.setToolTip(
            "关键词汇总月份（反查词池）：\n"
            "· 留空 = 近30天实时榜单\n"
            "· 填已归档历史月（如 202607）= 该月快照\n"
            "· 填当月会提示“快照未归档”（SellerSprite 服务端机制），请改已归档月份")
        self.month_edit.setFixedWidth(180)
        self.matrix_month_edit = QLineEdit()
        self.matrix_month_edit.setPlaceholderText("矩阵月份 yyyyMM（留空=近30天）")
        self.matrix_month_edit.setToolTip(
            "ASIN 矩阵月份：每个 ASIN 按该月查询自然/广告位排名与流量占比\n"
            "· 留空 = 近30天实时榜单（不跟随汇总月份）\n"
            "· 填已归档历史月（如 202601）= 该月快照（可独立于汇总月份）\n"
            "· 填当月会提示“快照未归档”（SellerSprite 服务端机制）")
        self.matrix_month_edit.setFixedWidth(180)
        row.addWidget(self.add_group_btn)
        row.addWidget(QLabel("任务名称："))
        row.addWidget(self.name_edit)
        row.addWidget(QLabel("汇总月份："))
        row.addWidget(self.month_edit)
        row.addWidget(QLabel("矩阵月份："))
        row.addWidget(self.matrix_month_edit)
        row.addStretch(1)
        lay.addLayout(row)

        # 预算
        self.budget_text = QPlainTextEdit()
        self.budget_text.setReadOnly(True)
        self.budget_text.setPlaceholderText("点击“核算预算”查看调用量明细…")
        self.budget_text.setMaximumHeight(150)
        lay.addWidget(self.budget_text)

        btn_row = QHBoxLayout()
        self.calc_btn = QPushButton("核算预算")
        self.calc_btn.clicked.connect(self._calc_budget)
        self.create_btn = QPushButton("创建任务并开始执行")
        self.create_btn.clicked.connect(self._create)
        btn_row.addWidget(self.calc_btn)
        btn_row.addWidget(self.create_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self._add_group()

    # ---------- 站点组 ----------

    def _add_group(self, marketplace: str = "US") -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        combo = QComboBox()
        for mp in sorted(MARKETPLACES):
            combo.addItem(mp)
        combo.setCurrentText(marketplace)
        asin_edit = QLineEdit()
        asin_edit.setPlaceholderText("如 B0GSXBMPY6, B0DJVXJL89…")
        node_edit = QLineEdit()
        node_edit.setPlaceholderText("类目 Node ID（可空）")
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda: self.table.removeRow(row))
        self.table.setCellWidget(row, 0, combo)
        self.table.setCellWidget(row, 1, asin_edit)
        self.table.setCellWidget(row, 2, node_edit)
        self.table.setCellWidget(row, 3, del_btn)

    def _collect_groups(self) -> list[dict]:
        groups = []
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0)
            asin_edit = self.table.cellWidget(row, 1)
            node_edit = self.table.cellWidget(row, 2)
            if combo is None:
                continue
            asin_text = asin_edit.text().strip() if asin_edit else ""
            node_text = node_edit.text().strip() if node_edit else ""
            if not asin_text and not node_text:
                continue
            groups.append({
                "marketplace": combo.currentText(),
                "asins": asin_text,
                "node_ids": node_text,
            })
        return groups

    # ---------- 预算 ----------

    def _calc_budget(self) -> None:
        try:
            task_input = prepare_task_input(self._groups_parsed(),
                                            self._month(), self._matrix_month())
        except ValidationError as exc:
            QMessageBox.warning(self, "输入校验失败", "\n".join(exc.errors))
            return
        budget = build_plan(task_input)
        self.budget_text.setPlainText("\n".join(budget.detail_lines()))
        self._last_input = task_input
        self._last_budget = budget

    def _groups_parsed(self) -> list[dict]:
        groups = self._collect_groups()
        parsed = []
        for g in groups:
            from app.core.input_validator import extract_asins

            parsed.append({
                "marketplace": g["marketplace"],
                "asins": extract_asins(g["asins"]),
                "node_ids": [n.strip() for n in g["node_ids"].split(",") if n.strip()],
                "node_top_n": 50,
            })
        return parsed

    def _month(self) -> str | None:
        m = self.month_edit.text().strip()
        return m or None

    def _matrix_month(self) -> str | None:
        m = self.matrix_month_edit.text().strip()
        return m or None

    # ---------- 创建 ----------

    def _create(self) -> None:
        try:
            task_input = prepare_task_input(self._groups_parsed(),
                                            self._month(), self._matrix_month())
        except ValidationError as exc:
            QMessageBox.warning(self, "输入校验失败", "\n".join(exc.errors))
            return
        budget = build_plan(task_input)
        total = budget.planned_total
        if total > CONFIRM_THRESHOLD:
            detail = "\n".join(budget.detail_lines())
            box = QMessageBox(self)
            box.setWindowTitle("预算确认")
            box.setIcon(QMessageBox.Warning)
            box.setText(f"预计调用 {total} 次（超过 {CONFIRM_THRESHOLD} 次，须确认）：\n\n{detail}\n\n继续创建任务？")
            box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            if box.exec() != QMessageBox.Ok:
                return

        # 多站点组：任务目录名取第一组站点与总 ASIN 数
        first = task_input["groups"][0]
        total_asins = sum(len(g["asins"]) for g in task_input["groups"])
        display_name = self.name_edit.text().strip() or None  # 仅列表显示名
        task_dir = self.store.create(first["marketplace"], total_asins,
                                     display_name=display_name)
        (task_dir / "input.json").write_text(
            json.dumps(task_input, ensure_ascii=False, indent=2), encoding="utf-8")
        (task_dir / "plan.json").write_text(json.dumps({
            "planned_total": budget.planned_total,
            "hard_cap": budget.effective_hard_cap,
            "confirmed": True,
            "confirmed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "detail": budget.detail_lines(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        self.store.log(task_dir, f"任务创建：{len(first['asins'])} ASIN，预算 {budget.planned_total} 次")
        self.on_created()
