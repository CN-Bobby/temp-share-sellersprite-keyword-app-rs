# SellerSprite关键词调研 v1.0.0 验收记录

验收日期：2026-08-29
应用版本：v1.0.0（重做版，替代 codex 测试版 v0.1.4）
内置报告引擎：skill v1.6.2（13 个脚本 / 13-Sheet Excel）
目标平台：Windows 10/11 x64

## 自动化测试

- **46 项测试全部通过**：限流窗口边界（8次/60s、7.5s 间隔）、预算公式（20ASIN=33、
  M1 单独批次、多站点组、纯 Node、趋势 cap）、输入校验（≤20 同站点/格式/月份）、
  密钥不落盘、调用日志 in_progress→补全、GUI 冒烟（双凭据保存/任务创建/入口启动/
  测试按钮读输入框回归）、离线端到端全流程（19 历史 ASIN 真实响应 fixture →
  Excel → 验收 73 项全绿）、断点续跑零新增调用。

## 真实冒烟（真实 MCP + 真实 DeepSeek）

- 20 个 US ASIN（历史任务合并），month=202606，全流程真实执行：
  - **33 次真实调用**（= ceil(20/20)×3 反查 + 20 矩阵 + 10 趋势，硬上限 35）：
    traffic_extend 3 页反查 + traffic_keyword 20 个 ASIN 矩阵 + aba_research_trend 10 个趋势词，
    8 次/分钟限流精确生效
  - 聚合 150 关键词（去重 0 冲突）→ 真实 DeepSeek（deepseek-v4-flash）标注 150 词
    （并发 3 路）→ 标签验收通过 → 趋势 10 词真实拉取（24 个月）→ 四段市场分析
    （model_split）→ Excel 生成 → **validate_report 73 PASS / 0 FAIL**
- 断点续跑验证：二次运行全部缓存命中，零新增 MCP 调用。

## 关键问题修复记录（v0.1.4 失败根因 + v1.0.0 实收问题）

| 问题 | 根因 | 修复 |
|---|---|---|
| LLM 分析空输出/截断（最顽固） | DeepSeek 思考模式默认开启；OpenAI 格式 `reasoning.enabled` 不被识别被静默忽略，思维链抢占输出预算 | 改用 `reasoning: {"effort": "none"}`（Responses）/ `thinking: {"type": "disabled"}`（Chat）；官方上下文 1M/输出 384K 实测无误 |
| 分析输入超限假象 | 旧版把 80 万字符矩阵全文塞进 prompt | 本地预计算（需求簇统计/象限候选/趋势摘要），词表按段裁剪 |
| 标注截断 | max_output_tokens 与批次组合不当 | 10 词/批 + 3 路并发 + 截断拆半 + 每批原子写回 |
| 并发标注数据竞态 | 写回与 json.dumps 并发 | write_lock 互斥 |
| 引擎脚本子进程乱码/失败 | Windows GBK 控制台 | 改为 runpy 同进程执行（打包后无独立解释器） |
| 真实 LLM schema 漂移 | evidence 等字段输出为数组/字符串 | 分析结果幂等规整层 |
| 设置页测试按钮误报"缺少凭据" | 测试读凭据管理器而非输入框 | 测试直接读输入框（保存才落盘） |
| 保存后凭据仍失效（打包版） | **pywin32 的 win32cred 依赖 win32timezone 未被 PyInstaller 收集**，打包版 CredWrite 抛 ModuleNotFoundError 且被静默吞掉 | build_exe 补 hidden-import win32timezone；CredentialStore 不再吞异常（仅 NOT_FOUND 返回 None）；GUI 保存失败弹窗提示；任务开始执行时自动登记设置页输入框凭据 |
| 默认模型名错误 | 默认值为已停用的旧别名 deepseek-chat | 默认改为 deepseek-v4-flash（/models 实测唯一可用名） |

## 打包验证

- exe --selfcheck 全绿（引擎资产/模板/执行链），GUI 启动正常。
- 敏感信息扫描：绿色目录无 SellerSprite Key / API Key 泄漏。
- 体积 142.6 MB（PySide6 运行时），目标电脑零依赖。

## 尚未覆盖

- 第二台干净 Windows 电脑实体机验收（建议首次分发前执行一次）。
- 多站点组任务、纯 Node 输入、M1（ASIN+Node）模式未做真实端到端（逻辑与预算
  已由单测覆盖，Node 接口参数已按官方 schema 校准）。
