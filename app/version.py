# -*- coding: utf-8 -*-
"""版本号唯一权威来源（SemVer）。

版本规范：
- PATCH（x.y.Z）：bug 修复（如 1.0.1）
- MINOR（x.Y.z）：新功能，向后兼容（Phase 2-5 开发 = 1.1.0）
- MAJOR（X.y.z）：不兼容协议/数据变更（2.0.0）

发布流程：功能开发 → 64+ 测试全绿 → CHANGELOG 更新 → 打包 →
git tag v<APP_VERSION> → 归档 发布/v<APP_VERSION>/（历史版本永不覆盖）。
回滚：git checkout vX.Y.Z 或直接从 发布/vX.Y.Z/ 取历史客户端。
"""
APP_VERSION = "1.3.2"  # 矩阵首列近30天实时标注窗口日期（截至采集日）
ENGINE_VERSION = "1.6.2"
APP_DISPLAY_NAME = "SellerSprite 关键词调研"

# 开发工具链标识：R/S = 由 Reasonix（AI 客户端）搭配 DeepSeek 大模型开发的应用版本
# （用于区分其他工具链开发的版本；随版本号一起标注）
DEV_CHAIN = "R/S"
