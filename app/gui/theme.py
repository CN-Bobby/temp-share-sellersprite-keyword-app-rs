# -*- coding: utf-8 -*-
"""全局 QSS 主题（Phase 4 页面美化：只作用样式层，不改控件结构与布局）。"""

QSS = """
* {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    font-size: 9.5pt;
    color: #263238;
}
QMainWindow, QWidget {
    background: #f5f7fa;
}
QGroupBox {
    border: 1px solid #d5dce4;
    border-radius: 6px;
    margin-top: 10px;
    padding: 10px 6px 6px 6px;
    background: #ffffff;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #1565c0;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #b0bec5;
    border-radius: 4px;
    padding: 5px 12px;
}
QPushButton:hover { background: #e3f2fd; border-color: #1565c0; }
QPushButton:pressed { background: #bbdefb; }
QPushButton:disabled { color: #9e9e9e; background: #eceff1; border-color: #cfd8dc; }
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {
    background: #ffffff;
    border: 1px solid #b0bec5;
    border-radius: 4px;
    padding: 4px 6px;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
    border: 1px solid #1565c0;
}
QComboBox::drop-down { border: none; width: 22px; }
QTableWidget {
    background: #ffffff;
    alternate-background-color: #f6f8fb;
    gridline-color: #e3e8ee;
    border: 1px solid #d5dce4;
    border-radius: 4px;
    selection-background-color: #e3f2fd;
    selection-color: #1565c0;
}
QTableWidget::item { padding: 4px 6px; }
QHeaderView::section {
    background: #eceff1;
    color: #37474f;
    font-weight: bold;
    border: none;
    border-bottom: 1px solid #cfd8dc;
    border-right: 1px solid #e0e5ea;
    padding: 6px;
}
QListWidget {
    background: #263238;
    border: none;
    color: #eceff1;
}
QListWidget::item { padding: 10px 14px; border-bottom: 1px solid #37474f; }
QListWidget::item:selected {
    background: #1565c0;
    color: #ffffff;
    border-left: 3px solid #82b1ff;
}
QSplitter::handle { background: #d5dce4; }
QScrollBar:vertical { background: #f5f7fa; width: 10px; }
QScrollBar::handle:vertical { background: #b0bec5; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QPlainTextEdit {
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 9pt;
    background: #fafbfc;
}
QLabel { background: transparent; }
"""

# 任务状态 → 颜色（列表状态列徽章）
PHASE_COLORS = {
    "done": "#2e7d32",       # 绿：完成
    "failed": "#c62828",     # 红：失败
    "canceled": "#e65100",   # 橙：已取消
    "created": "#78909c",    # 灰：已创建
    "collecting": "#1565c0",
    "aggregating": "#1565c0",
    "labeling": "#1565c0",
    "trends": "#1565c0",
    "analyzing": "#1565c0",
    "building": "#1565c0",
    "validating": "#1565c0",
    "unknown": "#90a4ae",
}

QUEUE_COLORS = {
    "done": "#2e7d32",
    "failed": "#c62828",
    "skipped": "#e65100",
    "running": "#1565c0",
    "queued": "#78909c",
}


def phase_color(phase: str) -> str:
    return PHASE_COLORS.get(phase, "#90a4ae")


def queue_color(state: str) -> str:
    return QUEUE_COLORS.get(state, "#90a4ae")
