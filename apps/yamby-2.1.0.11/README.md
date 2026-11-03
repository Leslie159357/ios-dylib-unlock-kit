# Yamby 2.1.0.11 arm64 解锁版 — 工程存档

清理解包树时保留的密钥、脚本与配方。2026-10-15。

## 成品
| 文件 | 大小 | sha256 |
|---|---|---|
| `Yamby_2.1.0.11_arm64_official_unlocked.apk` | 34,859,225 B | `8020162691201e3182d5c308393156c5761420e1244f4a405a5b624f2e53f4a4` |
| `Yamby_2.0.3.4_arm64_unlocked.apk` | 32,741,530 B | （早期版本，可覆盖） |

均在 `/opt/data/downloads/`。已由用户实机验证可用。

- 包名 `com.hush.yamby`，versionName 2.1.0.11，versionCode 20010012，minSdk 24 / targetSdk 36
- 纯 arm64-v8a，18 个 .so（娜迦 `libnmmp.so` / `libnmmvm.so` 原样保留）
- 自签 V1+V2+V3，同一把密钥 `yamby.keystore`（CN=Yamby Mod，口令 `yamby123`）→ 后续同密钥包可覆盖升级、无需卸载

## 原料
官方 arm64 单包（Telegram 官方频道 @yamby_release，用户转存至 115 网盘，pickcode `d18zer5u770imxl2s`）。
关键事实：官方单包与 APKPure 32 位分片 base 的 `classes.dex` / `classes2.dex` **逐字节相同**，故补丁集可整体移植到官方树，免去 split 合并。

## 补丁集（12 个文件，三类）
1. `ub/ۥۚۥۘۧ۠ۨ.smali` — 授权校验函数本体 → `const/4 v0, 0x1` + `return v0`
2. 10 处门禁站点 — 分支改 `goto` / `nop # gate-bypass`（清单见 `tree_diff.txt`）
3. flavor 串 `gpBundle` → `xxBundle`（让应用认为自己是非 Play 渠道包），同步改其 XOR+base64 形态：`W2khdcHO3po=` → `RGEhdcHO3po=`（位于 `a2/ۥۚۢۢۛۨ.smali`）

## 重建步骤（工具链在容器 rea-agent 内，宿主无 java/zipalign/apksigner）
```bash
docker exec -w /opt/data/cache/scratch/yamby rea-agent bash -lc '
  java -jar /opt/data/docker/rea-agent/apktool_3.0.3.jar d <官方包>.apk -o off_smali -f
  # 打补丁：移植 12 个文件（或用 patch_gates_*.py）
  bash build_off.sh          # 含 targetSdk34 私有色修正 → 重编译 → zipalign → apksigner
'
```
注意：容器解包树属 root，宿主侧改文件会 Permission denied，移植/修补要在容器内做。

## 文件
- `yamby.keystore` — Yamby 签名密钥（覆盖升级必须复用）
- `omap-debug.keystore` — Ovital 地图破解包用的 debug 密钥
- `patch_gates_v2.py` / `patch_gates_v3.py` / `patch_license_gates.py` — 门禁站点静态补丁脚本
- `fix_v34_colors.py` — Apktool 重编译 targetSdk34 私有色报错修正
- `build_off.sh` — 官方单包的完整构建脚本
- `transplant.sh` — 补丁文件移植脚本（容器内执行）
- `tree_diff.txt` — 补丁文件清单（diff -rq 输出）
- `yamby_pro.js` — Frida 兜底脚本（签名伪装 + 授权链 hook），若某版本校验未过可用
