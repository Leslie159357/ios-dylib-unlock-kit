# Doka 相机 2.2.15 逆向与解锁件（2026-10-27）

- `doka_unlock.c`      : 解锁 dylib 源码（纯 C / 零 SDK），v2 已去掉伪造 originalTransactionId
- `DokaCore_v2.dylib`  : 已 ad-hoc 签名的产物，弱加载注入到 Payload/Follow.app/Frameworks/
- `build_doka_ipa_v2.py`: 打包脚本（保留原包逐条目压缩，主二进制与 dylib 用 ZIP_STORED + 0755）
- `ida2215_1.log`      : IDA 定位日志（VipManager / NSUserDefaults 键 / 能力枚举）

## 结论
端侧会员判定被解锁（滤镜/CCD/去水印）。**AI 构图与精修在服务端按 installation 记每日额度**：
- `/security/v1/sessions` → lane=free, is_paid=false
- `/ai_camera/v2` → 429 `compose_daily_limit_reached`
- 客户端二进制中该错误码 0 命中；`ai.camera.v2.submit` 是服务端下发的能力枚举，非本地开关
- 二进制含 `installation_customer_mismatch` / `restricted_installation` 风控串 → 不建议刷 UUID 重置额度
