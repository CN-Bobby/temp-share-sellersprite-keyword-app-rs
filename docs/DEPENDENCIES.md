# 依赖清单

运行时由绿色包自带，目标电脑无需安装 Python、Node、MCP 客户端或任何运行时。

| 组件 | 版本 | 用途 |
|---|---:|---|
| CPython | 3.12.x | 应用运行时（内置） |
| PySide6 | 6.11.2 | Windows 桌面界面 |
| MCP Python SDK | 2.1.1 | SellerSprite Streamable HTTP 客户端 |
| httpx / httpx2 | 0.28.x / 2.12 | MCP 传输与 OpenAI 兼容模型 API |
| openpyxl | 3.1.5 | 13-Sheet Excel 生成 |
| Send2Trash | 2.1.0 | 任务目录移入 Windows 回收站 |
| pywin32 | 312 | Windows 凭据管理器（密钥存储） |
| PyInstaller | 6.22.2 | onedir 绿色打包（构建期依赖，不进分发） |

引擎脚本（`_internal/app/engine/scripts`）为 skill v1.6.2 官方脚本，仅依赖标准库 + openpyxl。
