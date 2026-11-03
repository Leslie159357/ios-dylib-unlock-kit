# ios-dylib-unlock-kit

iOS 付费功能解锁的**静态补丁 + dylib**工具集，Linux 侧完成，产出未签名 IPA。
收录 10 个已破解案例：源码、dylib 产物、补丁脚本与判定链报告都在 `apps/<app>/`。

不含任何 App 本体（IPA / 解密包），只放逆向结论、补丁脚本、自编译 dylib 与关键证据。
各案例 README 里出现的 `/opt/data/downloads/...ipa` 是当时本机构建路径，仓库不存这些包。

## 案例索引

| App | 判定位置 | 手段 | 产物 | 报告 |
|---|---|---|---|---|
| Scripting 3.2.1 | 端上（本地快照 + App Group 授权） | 序言补丁 + dylib（切 CloudKit） | `lib/ScriptingGroupFix.dylib` | `apps/scripting/REPORT.md` |
| OhMyCity 1.1.3 | 端上（StoreKit 2 本地验签） | 6 条 ARM64 指令补丁 | —（无 dylib） | `apps/ohmycity/REPORT.md` |
| Doka 相机 2.2.15 | 端上（VipManager / NSUserDefaults） | dylib | `DokaCore_v2.dylib` | `apps/doka-2.2.15/README.md` |
| Sketchbook 6.3 | 端上（`In_App_Purchases` 解密后比对 IDFV） | dylib | `SketchbookUnlock.dylib` | `apps/sketchbook-6.3/README.md` |
| Pigment 3.16 | 端上（RevenueCat + 本地到期日） | dylib | `PigmentUnlock.dylib` | `apps/pigment-3.16/REPORT.md` |
| 每日德语听力 26.10.2 / 26.10.4 | 端上（全局授权位；26.10.4 判定点未变，dylib 零改动复用，真机已验） | dylib | `TingDeVIP.dylib` | `apps/ting-de-26.10.4/README.md` |
| ColorPop AI | 端上（LedgerKit 本地收据算权益） | dylib | `ColorPopUnlock.dylib` | `apps/colorpop/REPORT.md` |
| 欧路词典 EuDic 系 | 端上（全局授权位 `0x64` 位掩码） | dylib | `EuDicUnlock.dylib` | `apps/eudic/REPORT.md` |
| LingoDeer 3.1.16 | 协议层 RSA+AES 双信封（Loon 无解） | dylib 短路会员判定 | `LingoDeer_unlock_dylib.dylib` | `apps/lingodeer/REPORT.md` |
| Yamby 2.1.0.11（Android） | smali 门禁（20 处校验调用 + flavor 常量） | APK 重打包 | `patch_gates_v2/v3.py` | `apps/yamby-2.1.0.11/复盘-逆向分析.md` |

| Facetune 26.36 | 端上（三路 OR 判定，Griffin 权益无效） | 7 条指令补丁 + group 改写（未验证已封存） | `scripts/patch_facetune.py` | `apps/facetune/REPORT.md` |

判断口诀：**回包里能找到 `is_pro` / `isPremium` 之类的字段 → 去写 Loon/QX；找不到 → 到这里来脱壳打补丁。**

## 什么时候走这条路

拿到 App 后先判一件事：**会员判定在服务端还是端上**。

- 服务端判定（RevenueCat / Adapty / 自家 API 回包里有 `is_pro` 之类字段）→ 走 Loon/QX 抓包重写，成本最低。
- 端上判定（StoreKit 2 本地校验、本地签名快照、本地 Keychain 状态）→ 网络层无从下手，只能动二进制或注入 dylib。

Scripting 属于后者：二进制里只有推送和官网两个域名，没有任何订阅接口；PRO 由 `EntitlementOracle` 读本地快照得出。所以这次不是 Loon 方案。

## 三种手段

| 手段 | 用在哪 | 例子 |
|---|---|---|
| ARM64 序言补丁 | Swift 布尔判定函数，`stp` 开头改成 `mov w0,#1; ret` | `EntitlementOracle.check`、`PurchaseManager.isProEnabled` |
| `LC_LOAD_DYLIB` 注入 | 需要在运行时替换行为（swizzle / interpose） | App Group 兜底、CloudKit 切断 |
| ObjC swizzle / dyld interpose | 系统框架调用点被硬编码，没法改 App 源码时 | `-[NSFileManager containerURLForSecurityApplicationGroupIdentifier:]`、`+[CKContainer containerWithIdentifier:]`、`SecTaskCopyValueForEntitlement` |

三者可以叠加。补丁负责「判定为真」，dylib 负责「环境缺失不崩」。

## 目录

```
apps/scripting/
  ScriptingFix.c                 # 最终 dylib 源码（App Group 兜底 + 切断 CloudKit）
  variant-entitlement-spoof.c    # 备选：伪造 iCloud entitlement 的变体
  REPORT.md                      # 完整逆向报告（判定链、崩溃根因、逐版修复）
  ida_*.txt                      # IDA 反编译证据
apps/ohmycity/
  patch_ohmycity.py              # 6 条指令补丁，带原指令 + 整包 sha256 校验
  REPORT.md                      # 抓包判定、@Observable 内联坑、判定链与补丁表
  ida_evidence.txt               # IDA 反汇编证据（结构体默认值 / apply / getter / setter）
apps/doka-2.2.15/                # 源码 + dylib + 打包脚本 + IDA 定位日志
apps/sketchbook-6.3/             # Hook.c + dylib + 打包脚本
apps/pigment-3.16/               # PigmentUnlock.c + dylib + 报告
apps/ting-de-26.10.2/            # TingDeVIP.m + dylib + 注入/探针脚本
apps/ting-de-26.10.4/            # 新版回归验证（判定点未变 + 复用注入记录）
apps/yamby-2.1.0.11/             # Android：smali 补丁脚本 + 复盘（不含 keystore）
apps/colorpop/                   # 报告 + dylib（MWM PublishingSDK/LedgerKit）
apps/eudic/                      # 报告 + dylib（EuDic 系全局授权位）
apps/lingodeer/                  # 报告（RSA+AES 双信封实证）+ dylib
scripts/
  patch_scriptingkit.py          # 按符号地址下序言补丁，带原指令校验
  inject_lc.py                   # 追加 LC_LOAD_DYLIB（利用 load commands 后空洞）
  repack_multi.py                # 按条目替换/新增重新打包 IPA
  build.sh                       # 一条龙：编译 dylib → 打补丁 → 注入 → 重打包
lib/
  ScriptingGroupFix.dylib        # 已编译产物（arm64 / iOS 17+）
```

## 快速用法

```bash
# 1. 交叉编译 dylib（需要 clang + ld64.lld， Linux 可跑）
docker run --rm -v "$PWD:/w" -w /w debian:bookworm bash -c '
  apt-get update -qq && apt-get install -y -qq clang lld >/dev/null &&
  clang -target arm64-apple-ios17.0 -dynamiclib -fuse-ld=lld -nostdlib -O2 \
        -Wl,-undefined,dynamic_lookup \
        -Wl,-install_name,@executable_path/Frameworks/ScriptingGroupFix.dylib \
        -o lib/ScriptingGroupFix.dylib apps/scripting/ScriptingFix.c'

# 2. 对目标二进制下序言补丁（地址来自 IDA）
python3 scripts/patch_scriptingkit.py <原始框架二进制> <输出路径>

# 3. 给主二进制追加 dylib 加载命令
cp Payload/App.app/App App.injected
python3 scripts/inject_lc.py App.injected \
        @executable_path/Frameworks/ScriptingGroupFix.dylib App.injected

# 4. 重新打包（manifest.json 里写 条目 → 本地文件）
python3 scripts/repack_multi.py 原包.ipa 输出.ipa manifest.json
```

签名自理：`Frameworks/` 下的 dylib 必须和主二进制一起重签，否则启动阶段会被内核拒绝。

## 三个必须踩过的坑

**1. 别用 C 可变参声明调 objc_msgSend。**
`extern id objc_msgSend(id, SEL, ...)` 在 Apple arm64 ABI 下会把可变实参**压栈**，
而 objc_msgSend 本体按 `x2/x3/x4` 读参 —— 传进去的指针会变成垃圾，段错误落在 `strlen`。
必须用精确原型的函数指针：

```c
typedef id (*Msg1)(id, SEL, id);
((Msg1)(void *)objc_msgSend)(obj, sel, a1);
```

同理，避开 `stringWithFormat:` 这类可变参方法，改用 `stringByAppendingPathComponent:` 逐级拼接。

**2. 侧载重签会吃掉 entitlement，而 App 往往是强制解包。**
典型崩溃：`containerURL(...)` 返回 nil → `__break(1u)`；`+[CKContainer containerWithIdentifier:]`
缺 iCloud 授权直接抛 NSException → SIGABRT。这两类都在 dylib 里兜底，不要试图改签名面板糊过去。

**3. SwiftUI `@Observable` 的属性，getter / setter 常常不是判定锚点。**
同模块 full-module 优化会把读内联成 `LDRB W?, [store,#off]`（不 `bl` getter），
写则走 `ObservationRegistrar.withMutation(of:keyPath:_:)` + 闭包直写内存（不调 setter）。
只改 getter/setter 会出现「补丁全打上了、装上毫无反应」。
正确落点是**状态写入的源头**：结构体默认值 + `apply(_:)` 里的读取指令。
OhMyCity 就是第一版改错位置、第二版才命中的典型案例（见 `apps/ohmycity/REPORT.md` 第 3 节）。

## 交付与清理约定

每次破解收尾固定两步，不留在机器上堆着：

1. **入库**：源码 + 补丁脚本 + dylib + 判定链报告进 `apps/<app>/`，并在上面的索引表加一行。
2. **清本地**：脱壳 IPA、成品 IPA、解包树、IDA 数据库、工作目录一律删掉；
   保留自研 App 构建与脱壳/越狱工具链（`fairplay-decrypt-*` + `credential.bin`、`dopamine`、`frida-server`）。

删前先判可重建性：`ipatool list-purchases` 里有的（自己已购）删了能重下重脱；
没有的（iOSGods、第三方源）删了回不来。

## 免责

仅用于自己已购或自测的 App。仓库不提供任何 App 二进制，产物需自行签名安装。
