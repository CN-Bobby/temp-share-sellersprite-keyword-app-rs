# tools/ 工具脚本索引

| 脚本 | 类别 | 用途 |
|---|---|---|
| `build_exe.py` | 构建 | PyInstaller onedir 打包（含引擎资产、hidden-import、文档补齐） |
| `smoke_live.py` | 冒烟 | 真实 MCP + 真实 LLM 全流程冒烟（20 ASIN，支持 --resume 断点续跑） |
| `rerun_user_task.py` | 冒烟 | 用指定旧任务 input.json 的 ASIN 清单重跑新任务（修复验证） |
| `check_sellersprite_live.py` | 验证 | 单独验证 SellerSprite MCP 可用性（list_tools + 最小业务调用） |
| `check_llm.py` | 验证 | 验证 LLM 凭据与协议模式（Responses/Chat） |
| `dump_mcp_schema.py` | 维护 | 拉取 MCP 工具 schema 存 tests/fixtures/mcp_tools_schema.json |
| `verify_batch_words.py` | 诊断 | 抽样验证两批 ASIN 的指定月/当前月词集交集 |
| `verify_matrix_month.py` | 诊断 | 验证 traffic_keyword 历史月与词池交集 |
| `verify_month_support.py` | 诊断 | 交叉验证 traffic_extend/traffic_keyword 的 month 支持性 |
| `verify_querytype.py` | 诊断 | 验证 traffic_extend queryType 与 traffic_keyword 词集一致性 |
| `debug_label.py` | 调试 | 真实 LLM 标注请求调试（打印 status/text_len） |
| `debug_market.py` | 调试 | 真实 LLM 分析段请求调试（按段） |
| `debug_matrix_gap.py` | 调试 | 检查矩阵记录与词池交集（交集 0 → 矩阵空白） |
| `diag_credentials.py` | 诊断 | 只读检查凭据管理器中的 key（掩码显示） |
| `fix_credentials.py` | 修复 | 修复凭据管理器残留（写回真实 key） |
| `version_info.txt` | 构建 | PyInstaller 版本资源文件 |

**使用约定**：诊断/调试脚本为一次性验证工具，运行完请删除其临时产物
（`tests/.tmp_*`），正式验证请走 `pytest` 与 `smoke_live.py`。
