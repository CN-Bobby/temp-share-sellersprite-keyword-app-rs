# -*- coding: utf-8 -*-
"""主窗口：左侧导航 + 右侧页面（设置 / 新建任务 / 任务列表）。"""
from __future__ import annotations

from PySide6.QtWidgets import (QHBoxLayout, QListWidget, QListWidgetItem,
                               QMainWindow, QStackedWidget, QVBoxLayout, QWidget)

from app.core.config import Settings
from app.core.task_store import TaskStore
from app.version import APP_DISPLAY_NAME, APP_VERSION

from .settings_page import SettingsPage
from .task_page import TaskCreatePage
from .tasks_page import TasksPage


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        self.settings = settings or Settings()
        self.store = TaskStore(self.settings.workspace_dir)
        self.setWindowTitle(f"{APP_DISPLAY_NAME} v{APP_VERSION}")
        self.resize(1080, 720)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.nav = QListWidget()
        self.nav.setFixedWidth(150)
        self.pages = QStackedWidget()
        self.settings_page = SettingsPage(self.settings)
        self.task_page = TaskCreatePage(self.settings, self.store, self._after_task_created)
        self.tasks_page = TasksPage(self.settings, self.store, self.settings_page)

        self.pages.addWidget(self.settings_page)
        self.pages.addWidget(self.task_page)
        self.pages.addWidget(self.tasks_page)

        for text in ("设置", "新建任务", "任务列表"):
            item = QListWidgetItem(text)
            item.setSizeHint(item.sizeHint().expandedTo(item.sizeHint()))
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)

        layout.addWidget(self.nav)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(central)

        self.nav.setCurrentRow(1)
        self.tasks_page.refresh()

    def _after_task_created(self) -> None:
        """新建任务后切到任务列表页。"""
        self.nav.setCurrentRow(2)
        self.tasks_page.refresh()
