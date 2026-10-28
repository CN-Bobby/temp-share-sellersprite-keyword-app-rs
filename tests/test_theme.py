# -*- coding: utf-8 -*-
"""Phase 4 主题测试：QSS 资源有效、状态颜色映射。"""
from app.gui import theme


def test_qss_nonempty_and_selectors():
    assert len(theme.QSS) > 1000
    # 关键控件样式选择器存在（美化不改布局）
    for sel in ("QPushButton", "QTableWidget", "QLineEdit", "QGroupBox",
                "QHeaderView", "QListWidget", "QSplitter"):
        assert sel in theme.QSS


def test_phase_colors():
    assert theme.phase_color("done") == "#2e7d32"
    assert theme.phase_color("failed") == "#c62828"
    assert theme.phase_color("created") == "#78909c"
    assert theme.phase_color("unknown-xxx") == "#90a4ae"  # 未知回退灰


def test_queue_colors():
    assert theme.queue_color("running") == "#1565c0"
    assert theme.queue_color("done") == "#2e7d32"
    assert theme.queue_color("skipped") == "#e65100"
