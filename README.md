# 临时公开分享副本：SellerSprite Keyword App（R/S）

此仓库是临时分享副本，任何人都可以访问。它是 Reasonix R/S 版本，不是 Codex 未完成开发版。

- 来源：`CN-Bobby/sellersprite-keyword-app-rs`，提交 `a6c30716a0669ea8803a4da4867b4432fc50430e`。
- 源仓库保持私有且未修改。
- 原有专有许可、代码、测试 fixtures 和数据均按请求保留；本副本没有更改其许可。

详见 [TEMPORARY_SHARE.md](TEMPORARY_SHARE.md)。

# SellerSprite 关键词调研（v1.1.0 · R/S）

> **R/S 版本**：本应用由 **Reasonix（AI 开发客户端）搭配 DeepSeek 大模型**开发；
> R/S 用于标识开发工具链（区别于其他工具链开发的版本），随版本号一起标注。

将 `sellersprite-market-keywords` skill（v1.6.2）脚本化为独立运行的 Windows 桌面小程序：
输入同站点 ASIN 清单（≤20/站点组，支持多站点组），自动完成 SellerSprite MCP 数据采集、
关键词标注、趋势分析、四段式 LLM 市场分析，产出 13-Sheet Excel 调研报告。

## 目录结构

```
.
├── app/                    # 应用源码
│   ├── main.py             # 入口（GUI / --selfcheck）
│   ├── core/               # 核心引擎：限流器、预算、MCP/LLM 客户端、流水线
│   ├── gui/                # PySide6 界面：设置 / 新建任务 / 任务列表
│   └── engine/             # skill v1.6.2 内置资产（scripts/references/assets，勿改）
├── tests/                  # pytest 测试（58 项：单元 + GUI 冒烟 + 离线端到端）
├── tools/                  # 开发/诊断工具脚本（用途索引见 tools/README.md）
├── docs/                   # 交付文档（README_启动说明 / ACCEPTANCE_REPORT / DEPENDENCIES / VERSION）
├── pyproject.toml          # 项目元数据、依赖、pytest 配置
├── requirements.txt        # 可复现依赖清单
└── 发布/                   # 分发产物（便携目录 + zip + SHA256，不入 git）
```

## 开发

```powershell
# 使用 Python 3.12 创建虚拟环境
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 测试
python -m pytest tests -q

# 运行
python app\main.py
python app\main.py --selfcheck
```

## 打包分发

```powershell
python tools\build_exe.py
# 产物：发布\SellerSprite关键词调研-v1.0.0-win-x64-portable\
```

## 合并约定（重要）

- 本仓库以 **git 基线提交** 为合并基础（三路合并）；`app/`、`tests/`、`tools/` 路径保持稳定
- 外部客户端修改回合并时：提供修改后的项目文件夹/zip，`git diff` 基线 → 逐文件核对合入
- `app/engine/` 为 skill v1.6.2 官方资产，合并不覆盖该目录（升级按 skill 发布包整体替换）
- 密钥永不入库：`app` 运行时密钥存 Windows 凭据管理器；仓库内不得出现真实 key

