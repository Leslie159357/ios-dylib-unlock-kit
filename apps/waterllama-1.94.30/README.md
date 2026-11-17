# Waterllama 喝水羊驼 1.94.30（build 1379）— Premium 解锁

`com.vitalii.water`，iPhone 17,2 / iOS 18.6.2 真机验证通过（2026-11-17）。
**Loon 无解**，走脱壳 + 20 条指令补丁。

---

## 一、为什么 Loon 不行

真机抓包（Loon 全量抓包 zip，冷启动窗口）只有 5 条报文，全是 Firebase Remote Config：

```
firebaseremoteconfigrealtime.googleapis.com  ×4
firebaseremoteconfig.googleapis.com          ×1   {"state":"NO_CHANGE","templateVersion":"61"}
```

`buy.itunes.apple.com/verifyReceipt` **一条都没有**。

反编译对上了原因：`validatePremiumFeaturesAccess`（0x1003568AC）在调 `verifyReceipt(forceRefresh: true)` 之前，先做 `Data(contentsOf: appStoreReceiptURL)`；读不到收据就直接跳过，一个包都不发。重签/无收据的机器上这条校验永远不会触发，网络层没有可改的报文。

> 注意：主二进制确实链接了 SwiftyStoreKit（`AppleReceiptValidator` + `verifyReceipt` 导入符号），单看符号会误判成「有网络校验、可以写 Loon」。真正的判据是**有没有实际请求**，不是有没有符号。

## 二、会员开关

`saveSubscriptionStatus(_:)` 里就一行：

```
setBool:<status+0x20> forKey:"purchaseState"
```

`status + 0x20` 这个 bool 就是全局会员位：7 处 `boolForKey:"purchaseState"` 读它，`validatePremiumFeaturesAccess` 也读它。没有任何签名校验、没有到期日计算、没有服务端。

`premiumPlanStartDate` 是另一个 key（用于 UI 显示起始日），不影响解锁。

## 三、补丁表（20 条）

`patch_waterllama.py` 里带原指令校验，版本不符会逐条报错中止。

### A. 会员位（8 条）

| vmaddr | 原指令 | 改为 | 位置 |
|---|---|---|---|
| 0x1003515DC | `bl objc_msgSend_boolForKey:` | `mov w0,#1` | 读 purchaseState #1 |
| 0x100352AC4 | 同上 | 同上 | #2 |
| 0x1004BDA70 | 同上 | 同上 | #3 |
| 0x1004BEA58 | 同上 | 同上 | #4 |
| 0x1004BFE78 | 同上 | 同上 | #5 |
| 0x1004C059C | 同上 | 同上 | #6 |
| 0x1004C1A18 | 同上 | 同上 | #7（Free/Premium 文案分支） |
| 0x1003534F0 | `ldrb w20,[x26,#0x20]` | `mov w20,#1` | 写入口强制 true |

### B. CloudKit 断链（5 条）

`+[CKContainer defaultContainer]` 在无 iCloud 权限的重签包上抛 `CKException` → `objc_exception_throw` → Swift 接不住 → SIGABRT。

| vmaddr | 原指令 | 改为 |
|---|---|---|
| 0x1005715D8 | `bl objc_msgSend_defaultContainer` | `mov w0,#0` |
| 0x100573520 | 同上 | 同上 |
| 0x1005769E8 | 同上 | 同上 |
| 0x100576A94 | 同上（首崩点） | 同上 |
| 0x100576E14 | 同上 | 同上 |

全二进制只有这 5 处 `defaultContainer`，没有 `containerWithIdentifier:` 调用点。

### C. 等待点（7 条）

容器为 nil 之后 completion 永不回来，主线程卡在 `dispatch_group_wait` 上被看门狗杀（`0x8BADF00D`，5s）。

| vmaddr | 原指令 | 改为 |
|---|---|---|
| 0x10057666C / 0x100576B34 / 0x100576E48 | `bl dispatch_group_wait` | `mov w0,#0` |
| 0x1006460F4 / 0x100649958 / 0x10064A894 / 0x10064BA00 | 同上 | 同上 |

## 四、两轮崩溃的根因（都跟会员补丁无关）

1. `Water-2026-11-17-093727.ips`：`EXC_CRASH / SIGABRT`，栈 `objc_exception_throw ← CloudKit ← dispatch_once`，返回地址 0x100576A98（即 0x100576A94 的 `defaultContainer`）。重签丢了 `com.apple.developer.icloud-container-identifiers`。
2. `Water-2026-11-17-095425.ips`：`SIGKILL`，`termination code 0x8BADF00D`「Failed to terminate gracefully after 5.0s」，主线程 `_dispatch_group_wait_slow ← 0x100576B38`。只把容器置 nil、没处理等待点导致的 hang。

教训：**在这个 App 上「切断 iCloud」必须同时处理三件事——建容器、回调、等待点**，只做前两件会从「崩」变成「卡死」。

## 五、复现

```bash
# 1. 取包（本账号已购）
ipatool download -b com.vitalii.water -o enc.ipa --purchase \
  --keychain-passphrase "$IPATOOL_KEYCHAIN_PASSPHRASE" --non-interactive

# 2. 脱壳（凭据见 /opt/data/credentials/account_680850235_key13/credential.bin）
python3 /opt/data/tools/fairplay-decrypt-v2/decrypt.py enc.ipa dec.ipa \
  --credential /opt/data/credentials/account_680850235_key13/credential.bin

# 3. 打补丁
python3 patch_waterllama.py Payload/Water.app/Water Water.patched

# 4. 重打包（去掉 _CodeSignature 与 embedded.mobileprovision）
zip -r Waterllama_1.94.30_premium_unsigned.ipa Payload/
```

原始脱壳二进制 sha256：`fd326619bb5c6c84c96914af82b87c71d28f9f44b3afdc24214c1982aa23fee4`（19,383,040 字节，cryptid=0）。

## 六、边界

- 只改了会员位与 iCloud 链路，其余逻辑原样。
- iCloud/CloudKit 同步在本包里是空转：本地数据（Realm）正常写入，云端不再同步，也不再弹同步相关提示。
- `premiumPlanStartDate` 未伪造，会员页「起始日期」可能显示为空或默认值，不影响功能。
