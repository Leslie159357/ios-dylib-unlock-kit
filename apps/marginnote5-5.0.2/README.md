# MarginNote 5 5.0.2 (build 2) — MAX 全量解锁 + 自定义 AI 侧载打通

bundle: `QReader.MarginStudy.easy` · iOS 17.0+ · arm64 thin · 上架更新 2026-11-10
加密包 306 MB → 脱壳包 273 MB（24 个 Mach-O / 14844 页），主二进制 60.1 MB
成品：`MarginNote5_5.0.2_v7_unsigned.ipa`（272.3 MB，sha256 `922838b7e7f04e1d2400ef18a1236e9862acc3cdca5fb2e99c804610a37baf57`）
状态：**用户真机安装确认解锁可用**（2026-11-13）

## 结论先行

- **Loon 无解**：权益来自本地收据（`RMStoreAppReceiptVerifier` 本地验签 → `MNEntitlementResolver`
  生成 `MNEntitlementSnapshot`），没有服务端权益接口可改写；二进制里的 `verifyReceipt` URL
  是库里的死字符串，实测无代码引用。
- 走 IPA + dylib。**5.0.0 那套固定偏移静态补丁全部作废**：5.0.0→5.0.2 代码整体重排
  （`tier` 从 0x1005a9xxx 挪到 0x100a8xxx）。本版 dylib 只按「类名 + selector 名」查找方法，
  小版本更新不需要重新找偏移。
- 5.0.2 新增了 CloudKit 拉配置的一整族方法（service keys / AI 模型路由 / addon 证书），
  自签包没有 iCloud 授权会连环抛 `CKException` → `SIGABRT`。这是本次主要工作量。

## 解锁范围

| 目标 | 实现 |
|---|---|
| MAX 全量权益 | `-[MNEntitlementSnapshot tier]` → 2；`receiptValid`/`hasProLifetime`/`hasMaxLifetime`/`hasActiveFullMaxSubscription`/`hasActiveLegacyMaxUpgradeSubscription`/`hasLegacyMaxUpgradeLifetime`/`hasSharedPremiumMax`/`hasAnyActiveMax` → 1 |
| 到期时间 | `maxExpirationDate`/`sharedMaxExpirationDate` → `NSDate dateWithTimeIntervalSince1970:4102444800`（2100-01-01） |
| OCR Pro / Pro 产品 / Premium Connect | `-[AppDelegate_iPad isValidOCRPro]`、`isValidOCRProInternal:`、`isValidOCRProInternal:excludeTrial:`、`isValidProduct`、`isValidPremiumConnect` → 1（`isValidProduct` 是覆盖面最广的闸，BookViewController 内十余处调用） |
| 购买记录 | `RMStoreUserDefaultsPersistence` / `RMStoreKeychainPersistence` `isPurchasedProductOfIdentifier:` → 1 |
| AI 额度 | `MBCreditManager` `maxCredit0/1`、`remainingCredit0/1` → 999999；`currentCredit0/1` → 0；`hasEnoughCredit0:/1:` → 1 |
| 自定义 AI（MAX） | `+hasCustomAIMaxEntitlement` → 1；`customAIActiveAPIKeyMatchesBoundProfile` → 1；`customAIInternalKeyValidationResultForAPIKey` → 0；Keychain 读写 hook 成恒定成功/回填 key；`testPendingCustomAIProfileWithCompletion` 直接回调成功（防侧载栈 block 崩溃） |
| 自定义 AI 自动配置 | 首次 `+[MNEntitlementResolver currentSnapshot]`（或 `-[AppDelegate_iPad isValidProduct]`）时调 `savePendingCustomAIBaseURL:apiKey:miniModel:normalModel:` + `bindPendingCustomAIProfileAfterSuccessfulTest`，启动即写入，无需进设置点「测试并绑定」 |

## 崩溃链（自签包 / CloudKit）

签名后 App 启动即 `SIGABRT`，`objc_exception_throw` 来自 `CloudKit`（`CKSDKVersion` →
`CKMainBundleIsAppleExecutable`），根因是 App 没有 `com.apple.developer.icloud-container-identifiers`
授权，建 `CKContainer` 必抛 `CKException`。逐条定位（三份 ips）：

| # | 崩溃返回地址 | 路径 | 处理 |
|---|---|---|---|
| 1 | `0x1f3c5e0` | 启动同步：`+[iCloudSyncManager activateDB:]` 内 `[CKContainer containerWithIdentifier:]` | 6 处调用点改 `mov x0,#0`（init 4 处 + activateDB + checkActivationLive） |
| 2 | `0x1f40a2c` | 定时任务 `-[AppDelegate_iPad refreshAIModelRoutingFromCloudKitIfNeeded]` → `fetchModelRoutingConfigInternal:completionHandler:` 内 `CKContainer` 分配 | hook 该方法为空实现 |
| 3 | `0x1f40140` | 定时任务 `fetchServiceKeys:` → `fetchServiceKeysInternal:completionHandler:` | hook 空实现 |
| 4 | `0x1f41370` / `0x1f41900` | `fetchAddonCertifications:` → `mn_fetchAddonCertificationPageWithCursor:validCertKeys:pageNumber:completionHandler:` | hook 空实现 |
| 5 | 最终 | 上述只是同一个模式的不同入口，补不完 | **根上掐**：`-[iCloudSyncManager init]` 返回 nil，实例级 CK 全部变空消息；`+activateDB:` / `+checkActivationLive` 保持原样运行（只把其中建容器改成 nil），因此不会出现「启动一直转圈」 |

关键教训：**不能把 `activateDB:` / `checkActivationLive` 整个方法 no-op**
（v2 由此导致启动卡在转圈：启动流程在等这两个方法里的状态回调）；
也不能把 Swift 侧 29 处 `containerWithIdentifier` 调用点塞 nil（Swift 非可选解包会换成另一种崩溃）。

## 静态补丁（`patch_binary.py`，文件偏移 = VA - 0x100000000）

| VA | 原 | 改 | 说明 |
|---|---|---|---|
| `0x1018f4580` | `tbz w0,#0` | `1f2003d5` NOP | bind：receipt 必须是 NSString |
| `0x1018f460c` | `tbz w20,#0` | `1f2003d5` NOP | bind：六项测试标志 / 策略版本 / 收据哈希 |
| `0x1018f49bc` | `mov x28,x0` | `movz x28,#1` (`3c0080d2`) | bind：Keychain 结果强写成功 |
| `0x101eb7c24/7c50/7c94`、`0x101eb8eb4` | `BL containerWithIdentifier` | `mov x0,#0` | `-[iCloudSyncManager init]` |
| `0x101f3c150` | 同上 | `mov x0,#0` | `+checkActivationLive` |
| `0x101f3c5dc` | 同上 | `mov x0,#0` | `+activateDB:` |

`containerWithIdentifier` 全文共 35 个调用点，其余 29 处（Swift 同步引擎内部）不动。

## dylib 设计要点

- 纯 C，无 SDK，`__attribute__((constructor))` 里用 `objc_getClass` /
  `class_copyMethodList` / `method_setImplementation` 装 hook。
- **按名字查方法**，且「精确名优先、否则前缀匹配」：这版二进制的 `__objc_methname`
  把部分长 selector 截断成 `savePendingCustomAIBaseURL:apiKey:miniMo...del:` 这种带省略号的形态，
  直接 `sel_registerName` 会查不到。`MNEntitlementResolver currentSnapshot` 是**类方法**，
  早期版本按实例方法查所以一直 `method missing`。
- 日志写到 `$HOME/Documents/mn5hook.log`（Info.plist 打开 `UIFileSharingEnabled`，
  「文件」App 里可读），每装一条 hook 打一行 `[o]/[x]`，便于下一版回归。

## 自定义 AI 端点（key 不进包）

App 内 baseURL 指向自有域名反代，上游 key 只在服务端注入：

```
location /probe/mn/<token>/ {
    proxy_pass https://amr-link.open-design.ai/;
    proxy_http_version 1.1;
    proxy_set_header Host amr-link.open-design.ai;
    proxy_set_header Authorization "Bearer <upstream key>";
    proxy_set_header Connection "";
    proxy_ssl_server_name on;
    proxy_buffering off;          # SSE 必须
    proxy_read_timeout 600s;
}
```

模型槽：mini = `deepseek-v4.1-flash`（唯一带 image 输入）、normal = `deepseek-v4.1-flash-eco`。
`deepseek-v4.1-flash-eco` 是纯文本模型，填到两个槽会导致图片类 AI 任务失败。

## 构建 / 打包

```sh
# 1. dylib（容器内，clang + ld64.lld）
sh build.sh mn5hook.c mn5hook.dylib

# 2. 主二进制静态补丁
python3 patch_binary.py "Payload/MarginNote 5.app/MarginNote 5"

# 3. 注入弱依赖 + 放 dylib
cp mn5hook.dylib "Payload/MarginNote 5.app/Frameworks/mn5hook.dylib" && chmod 755 ...
python3 inject_weak.py "Payload/MarginNote 5.app/MarginNote 5" @executable_path/Frameworks/mn5hook.dylib

# 4. Info.plist 加 UIFileSharingEnabled / LSSupportsOpeningDocumentsInPlace，显示名改 MarginNote 5 Pro
# 5. 重打包（所有 Mach-O 保持 755）
python3 repack.py . ../MarginNote5_5.0.2_v7_unsigned.ipa
```

## 已知限制

- iCloud 同步不可用（设置里显示未启用/未登录）。这是自签证书拿不到 iCloud 授权导致的，
  不是补丁副作用；本地笔记、PDF、OCR、Max 权益、自定义 AI 均不受影响。
- 未签名包，安装需 LcSign / 全能签自签，签名时保留原版 Entitlements。
- 自定义 AI 的「测试并绑定」按钮被 hook 成直接成功，不要指望它真的去测端点。

## 分发

<https://dl.1122275.xyz/MarginNote5_5.0.2_v7_unsigned.ipa>
