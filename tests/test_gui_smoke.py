# -*- coding: utf-8 -*-
"""GUI 冒烟测试：offscreen 模式验证页面结构、设置保存、任务创建流程。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.task_store import TaskStore  # noqa: E402

pytestmark = pytest.mark.gui


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    instance = QApplication.instance() or QApplication([])
    yield instance


def _make_window(tmp_path):
    from app.gui.main_window import MainWindow

    settings = Settings(app_dir=tmp_path / "app",
                        cred_prefix="SellerSpriteKeywordAppTest")  # 测试隔离前缀，绝不污染真实凭据
    settings.workspace_dir = str(tmp_path / "ws")
    settings.window_max_calls = 1000
    settings.min_call_interval = 0.0
    win = MainWindow(settings)
    return win, settings


def test_main_window_structure(app, tmp_path):
    win, settings = _make_window(tmp_path)
    assert win.nav.count() == 3
    assert win.pages.count() == 3
    # 默认跳到新建任务页
    assert win.nav.currentRow() == 1
    win.close()


def test_app_entrypoint_starts_and_quits(app, tmp_path, monkeypatch):
    """app.main 入口：启动窗口并自动退出，验证无初始化崩溃。"""
    from PySide6.QtCore import QTimer

    from app.main import main

    import app.core.config as config_mod

    monkeypatch.setattr(config_mod, "default_workspace_dir",
                        lambda: str(tmp_path / "ws"))

    def _quit():
        app.quit()

    QTimer.singleShot(800, _quit)
    code = main()
    assert code == 0


def test_settings_save_and_credentials(app, tmp_path):
    win, settings = _make_window(tmp_path)
    page = win.settings_page
    page.mcp_url_edit.setText("https://mcp.sellersprite.com/mcp")
    page.mcp_key_edit.setText("TMP_GUI_KEY")
    page.llm_url_edit.setText("https://api.deepseek.com")
    page.llm_key_edit.setText("TMP_LLM_KEY")
    page.llm_model_edit.setText("deepseek-chat")
    page._save()
    assert settings.mcp_secret_key == "TMP_GUI_KEY"
    assert settings.llm_api_key == "TMP_LLM_KEY"
    assert settings.llm_model == "deepseek-chat"
    # 清理凭据
    settings.credentials.delete("mcp_secret_key")
    settings.credentials.delete("llm_api_key")
    win.close()


def test_task_create_page_flow(app, tmp_path):
    win, settings = _make_window(tmp_path)
    store = TaskStore(settings.workspace_dir)
    created: list[str] = []

    from app.gui.task_page import TaskCreatePage

    page = TaskCreatePage(settings, store, on_created=lambda: created.append("ok"))
    # 默认一行；填 ASIN
    asin_edit = page.table.cellWidget(0, 1)
    asin_edit.setText("B0GSXBMPY6, B0DJVXJL89")
    page.month_edit.setText("202606")
    page._calc_budget()
    assert "预计总调用" in page.budget_text.toPlainText()
    page._create()
    assert created == ["ok"]
    # 任务目录与 input.json / plan.json
    tasks = store.list_tasks()
    assert len(tasks) == 1
    task_dir = store.tasks_dir / tasks[0]["dir"]
    assert (task_dir / "input.json").exists()
    assert (task_dir / "plan.json").exists()
    win.close()


def test_settings_page_prefills_defaults_without_settings_file(app, tmp_path):
    """分发版保障：无 settings.json 时设置页预填 DeepSeek 默认 URL/模型，
    用户只填 API key 即可（key 永不预填/落盘）。"""
    win, settings = _make_window(tmp_path)
    page = win.settings_page
    assert page.llm_url_edit.text() == "https://api.deepseek.com"
    assert page.llm_model_edit.text() == "deepseek-v4-flash"
    assert page.mcp_url_edit.text() == "https://mcp.sellersprite.com/mcp"
    assert page.llm_key_edit.text() == ""  # key 必须留空由用户填
    assert page.mcp_key_edit.text() == ""
    win.close()


def test_task_create_with_display_name(app, tmp_path):
    """Phase 2：新建任务填写自定义名称 → task.json 记录 display_name。"""
    win, settings = _make_window(tmp_path)
    store = TaskStore(settings.workspace_dir)
    created: list[str] = []

    from app.gui.task_page import TaskCreatePage

    page = TaskCreatePage(settings, store, on_created=lambda: created.append("ok"))
    asin_edit = page.table.cellWidget(0, 1)
    asin_edit.setText("B0GSXBMPY6, B0DJVXJL89")
    page.name_edit.setText("泳装 2026 旺季")
    page._create()
    assert created == ["ok"]
    tasks = store.list_tasks()
    assert tasks[0]["display_name"] == "泳装 2026 旺季"
    # 目录名保持自动格式（不受显示名影响）
    assert "泳装" not in tasks[0]["dir"]
    state = store.read_state(store.tasks_dir / tasks[0]["dir"])
    assert state["display_name"] == "泳装 2026 旺季"
    win.close()


def test_tasks_page_refresh_shows_display_name(app, tmp_path):
    """Phase 2：列表显示自定义名，tooltip 保留真实目录名。"""
    win, settings = _make_window(tmp_path)
    store = TaskStore(settings.workspace_dir)
    d = store.create("US", 5, display_name="测试命名")
    win.tasks_page.refresh()
    name_item = win.tasks_page.table.item(0, 0)
    assert name_item.text() == "测试命名"
    assert name_item.data(0x0100) == d.name  # UserRole 存真实目录名
    win.close()


def test_queue_start_filters_done_tasks(app, tmp_path, monkeypatch):
    """Phase 3：一键排队只含未完成任务（done 跳过）。"""
    win, settings = _make_window(tmp_path)
    store = TaskStore(settings.workspace_dir)
    d1 = store.create("US", 5)
    d2 = store.create("US", 5)
    d3 = store.create("US", 5)
    store.set_phase(d1, "done")
    # 三个任务都“选中”：直接填充队列路径（绕过选择交互）
    page = win.tasks_page
    info = []
    monkeypatch.setattr("app.gui.tasks_page.QMessageBox.information",
                        lambda *a, **k: info.append(a))
    monkeypatch.setattr("app.gui.tasks_page.QMessageBox.warning",
                        lambda *a, **k: None)
    # 绕过 UI 选择交互：直接指定选中集合
    monkeypatch.setattr(page, "_selected_dirs",
                        lambda: [d1.name, d2.name, d3.name])
    for d in (d2, d3):
        (d / "input.json").write_text("{}", encoding="utf-8")
    # mock worker：只记录启动，不真跑
    started = []

    class FakeWorker:
        def __init__(self, settings, task_dir, store):
            self.task_dir = task_dir
            self.finished = self._Sig()
            started.append(task_dir.name)

        class _Sig:
            def connect(self, fn):
                pass

        def start(self):
            pass

        def cancel(self):
            pass

        def isRunning(self):
            return False

    monkeypatch.setattr("app.gui.tasks_page.PipelineWorker", FakeWorker)
    # 凭据就位（隔离前缀）让 _launch_task 真正启动 FakeWorker
    monkeypatch.setattr(page, "_maybe_autosave_credentials", lambda: None)
    settings.mcp_secret_key = "M"
    settings.llm_base_url = "https://x"
    settings.llm_api_key = "L"
    settings.llm_model = "m"
    page._start_queue()
    assert page.queue == [d2.name, d3.name]  # done 任务不入队
    assert started == [d2.name]  # 队列串行：仅当前任务被启动
    assert page.queue_results[d2.name] == "running"
    assert page.queue_results[d3.name] == "queued"
    settings.credentials.delete("mcp_secret_key")
    settings.credentials.delete("llm_api_key")
    assert d1.name not in page.queue
    win.close()


def test_queue_advances_on_done_and_failed(app, tmp_path, monkeypatch):
    """Phase 3：单任务结束（成功/失败）自动推进下一个，失败跳过不中断。"""
    win, settings = _make_window(tmp_path)
    store = TaskStore(settings.workspace_dir)
    d1 = store.create("US", 5)
    d2 = store.create("US", 5)
    d3 = store.create("US", 5)
    for d in (d1, d2, d3):
        (d / "input.json").write_text("{}", encoding="utf-8")
    page = win.tasks_page
    info = []
    monkeypatch.setattr("app.gui.tasks_page.QMessageBox.information",
                        lambda *a, **k: info.append(a))
    monkeypatch.setattr("app.gui.tasks_page.QMessageBox.warning",
                        lambda *a, **k: None)
    monkeypatch.setattr(page, "_maybe_autosave_credentials", lambda: None)
    # 凭据已就位
    settings.mcp_secret_key = "M"
    settings.llm_base_url = "https://x"
    settings.llm_api_key = "L"
    settings.llm_model = "m"

    started = []

    class FakeWorker:
        def __init__(self, settings, task_dir, store):
            self.task_dir = task_dir
            self.finished = self._Sig()

        class _Sig:
            def connect(self, fn):
                self.fn = fn

        def start(self):
            started.append(self.task_dir.name)

        def cancel(self):
            pass

        def isRunning(self):
            return False

    monkeypatch.setattr("app.gui.tasks_page.PipelineWorker", FakeWorker)
    page.queue = [d1.name, d2.name, d3.name]
    page.queue_index = 0
    page.queue_results = {n: "queued" for n in page.queue}
    page.queue_btn.setEnabled(False)
    page.queue_stop_btn.setEnabled(True)
    page._run_next()
    assert started == [d1.name]
    # 任务 1 成功 → 自动推进任务 2
    store.set_phase(d1, "done")
    page._on_worker_finished()
    assert page.queue_results[d1.name] == "done"
    assert started == [d1.name, d2.name]
    # 任务 2 失败 → 跳过，推进任务 3
    store.set_phase(d2, "failed", "注入失败")
    page._on_worker_finished()
    assert page.queue_results[d2.name] == "failed"
    assert started == [d1.name, d2.name, d3.name]
    # 任务 3 成功 → 队列完成（_finish_queue 清空队列与结果并弹汇总）
    store.set_phase(d3, "done")
    page._on_worker_finished()
    assert page.queue_index == -1
    assert page.queue_results == {}
    assert any("队列执行完成" in str(a) for a in info)
    settings.credentials.delete("mcp_secret_key")
    settings.credentials.delete("llm_api_key")
    win.close()


def test_queue_stop_skips_remaining(app, tmp_path, monkeypatch):
    """Phase 3：停止队列 → 剩余任务 skipped，当前结束后汇总不再推进。"""
    win, settings = _make_window(tmp_path)
    store = TaskStore(settings.workspace_dir)
    d1 = store.create("US", 5)
    d2 = store.create("US", 5)
    page = win.tasks_page
    page.queue = [d1.name, d2.name]
    page.queue_index = 0
    page.queue_results = {d1.name: "running", d2.name: "queued"}
    page.worker = None
    page._stop_queue()
    assert page.queue_results[d2.name] == "skipped"
    assert page.queue_index == len(page.queue)  # 直接到队尾
    # 当前任务结束后触发汇总（不启动 d2）
    started = []

    class FakeWorker:
        def __init__(self, settings, task_dir, store):
            self.task_dir = task_dir
            self.finished = self._Sig()

        class _Sig:
            def connect(self, fn):
                self.fn = fn

        def start(self):
            started.append(self.task_dir.name)

        def cancel(self):
            pass

        def isRunning(self):
            return False

    monkeypatch.setattr("app.gui.tasks_page.PipelineWorker", FakeWorker)
    monkeypatch.setattr("app.gui.tasks_page.QMessageBox.information",
                        lambda *a, **k: None)
    store.set_phase(d1, "canceled")
    page.current_task = d1.name
    page._on_worker_finished()
    assert started == []  # 没有启动下一个
    assert page.queue_index == -1
    assert page.queue_results == {}
    win.close()


def test_task_over_20_blocked_in_gui(app, tmp_path):
    win, settings = _make_window(tmp_path)

    from app.gui.task_page import TaskCreatePage

    page = TaskCreatePage(settings, TaskStore(settings.workspace_dir), on_created=lambda: None)
    asin_edit = page.table.cellWidget(0, 1)
    asin_edit.setText(", ".join(f"B0A{i:07d}" for i in range(21)))
    # 创建应被校验层拒绝（QMessageBox 弹窗在无头模式下不可交互，直接验证校验函数）
    from app.core.input_validator import ValidationError

    from app.core.pipeline import prepare_task_input

    with pytest.raises(ValidationError):
        prepare_task_input(page._groups_parsed(), None)
    win.close()


def test_task_starts_with_unset_credential_store_but_filled_inputs(app, tmp_path, monkeypatch):
    """修复回归：只填了设置页输入框（未点测试/保存）时，任务页开始执行应自动登记，
    不再弹"请先填写"。"""
    win, settings = _make_window(tmp_path)
    # 清理隔离前缀下的历史残留（其他测试中途失败可能遗留）
    settings.credentials.delete("mcp_secret_key")
    settings.credentials.delete("llm_api_key")
    sp = win.settings_page
    sp.mcp_url_edit.setText("https://mcp.sellersprite.com/mcp")
    sp.mcp_key_edit.setText("TMP_GUI_KEY")
    sp.llm_url_edit.setText("https://api.deepseek.com")
    sp.llm_key_edit.setText("TMP_LLM_KEY")
    sp.llm_model_edit.setText("deepseek-v4-flash")
    assert not settings.has_mcp_credentials()
    # 直接验证自动登记方法（_start 全流程会启动真实 worker，不在此触发）
    win.tasks_page._maybe_autosave_credentials()
    assert settings.mcp_secret_key == "TMP_GUI_KEY"
    assert settings.llm_api_key == "TMP_LLM_KEY"
    assert settings.llm_model == "deepseek-v4-flash"
    settings.credentials.delete("mcp_secret_key")
    settings.credentials.delete("llm_api_key")
    win.close()


def test_autosave_does_not_overwrite_with_empty_inputs(app, tmp_path, monkeypatch):
    """防呆：输入框为空时不得覆盖已保存的凭据。"""
    win, settings = _make_window(tmp_path)
    settings.mcp_secret_key = "EXISTING_KEY"
    settings.llm_api_key = "EXISTING_LLM"
    # 输入框为空
    win.tasks_page._maybe_autosave_credentials()
    assert settings.mcp_secret_key == "EXISTING_KEY"
    assert settings.llm_api_key == "EXISTING_LLM"
    settings.credentials.delete("mcp_secret_key")
    settings.credentials.delete("llm_api_key")
    win.close()
    win, settings = _make_window(tmp_path)

    from app.gui.task_page import TaskCreatePage

    page = TaskCreatePage(settings, TaskStore(settings.workspace_dir), on_created=lambda: None)
    asin_edit = page.table.cellWidget(0, 1)
    asin_edit.setText(", ".join(f"B0A{i:07d}" for i in range(21)))
    # 创建应被校验层拒绝（QMessageBox 弹窗在无头模式下不可交互，直接验证校验函数）
    from app.core.input_validator import ValidationError

    from app.core.pipeline import prepare_task_input

    with pytest.raises(ValidationError):
        prepare_task_input(page._groups_parsed(), None)
    win.close()


def test_test_mcp_uses_input_box_not_credential_store(app, tmp_path, monkeypatch):
    """修复回归：测试连接应直接读取输入框，不依赖未保存的凭据管理器值。"""
    win, settings = _make_window(tmp_path)
    page = win.settings_page
    # 凭据管理器为空（模拟新用户刚填 key 未保存）
    assert settings.mcp_secret_key == ""
    page.mcp_url_edit.setText("https://mcp.sellersprite.com/mcp")
    page.mcp_key_edit.setText("TMP_GUI_KEY")
    warnings = []
    monkeypatch.setattr("app.gui.settings_page.QMessageBox.warning",
                        lambda *a, **k: warnings.append(a))
    received = {}

    def _fake_test(endpoint):
        received["endpoint"] = endpoint
        return {"ok": True, "tools": 5}

    monkeypatch.setattr("app.core.mcp_client.test_mcp_connection", _fake_test)
    page._test_mcp()
    # 等后台测试线程完成
    for _ in range(100):
        app.processEvents()
        if received:
            break
        import time
        time.sleep(0.02)
    assert not warnings  # 不再误报"请先填写"
    assert received["endpoint"] == "https://mcp.sellersprite.com/mcp?secret-key=TMP_GUI_KEY"
    # 测试通过后自动登记凭据（on_ok 回调执行 _collect + save）
    for _ in range(100):
        app.processEvents()
        if settings.mcp_secret_key == "TMP_GUI_KEY":
            break
        import time
        time.sleep(0.02)
    assert settings.mcp_secret_key == "TMP_GUI_KEY"
    settings.credentials.delete("mcp_secret_key")
    settings.credentials.delete("llm_api_key")
    win.close()


def test_test_llm_uses_input_box_not_credential_store(app, tmp_path, monkeypatch):
    """修复回归：测试模型应直接读取输入框，不依赖未保存的凭据管理器值。"""
    win, settings = _make_window(tmp_path)
    page = win.settings_page
    assert settings.llm_api_key == ""
    page.llm_url_edit.setText("https://api.deepseek.com")
    page.llm_key_edit.setText("TMP_LLM_KEY")
    page.llm_model_edit.setText("deepseek-chat")
    warnings = []
    monkeypatch.setattr("app.gui.settings_page.QMessageBox.warning",
                        lambda *a, **k: warnings.append(a))
    page._test_llm()
    assert not warnings  # 不再误报"请填写 Base URL、API Key 与模型名"
    # 等待后台测试线程结束（无 mocked 网络，线程会真实失败但不应弹窗）
    for _ in range(50):
        app.processEvents()
        import time
        time.sleep(0.02)
    win.close()


def test_test_mcp_warns_when_input_empty(app, tmp_path, monkeypatch):
    """输入框为空时仍应提示。"""
    win, settings = _make_window(tmp_path)
    page = win.settings_page
    warnings = []
    monkeypatch.setattr("app.gui.settings_page.QMessageBox.warning",
                        lambda *a, **k: warnings.append(a))
    page.mcp_key_edit.setText("")
    page._test_mcp()
    assert len(warnings) == 1
    win.close()
