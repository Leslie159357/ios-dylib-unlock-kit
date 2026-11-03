# Facetune 26.36 (10288) com.lightricks.Facetune2 — VIP 二进制补丁

补丁内容：`mov w0,#1 ; ret` (20008052 c0035fd6)

| VA | 文件偏移 | 符号 |
|---|---|---|
| 0x101071dd8 | 0x1071dd8 | -[LegacyUserSubscriptionStateProvider hasVIPAccess] |
| 0x10383d600 | 0x383d600 | -[BZRSubscriptionState isUserSubscriber] |
| 0x10010744c | 0x10744c  | -[FTFeatureState hasVIPAccess] |
| 0x10012cf60 | 0x12cf60  | -[FTFeatureViewModel hasVIPAccess] |
| 0x10012e76c | 0x12e76c  | -[FTLegacyState hasVIPAccess] |

未改：FTFeature*Item/FTFiltersProcessor 的 isVIP —— 那是"该功能是否属于 VIP"的静态数据，改了会把全部功能锁死。

原始字节：f44fbea9fd7b01a9 (前两个)，e8cb039008f58db9 / 002c4039c0035fd6 / a8ca03b0083d8eb9

## v2 追加（修复启动闪退 SIGABRT）
| 0x103e691a4 | 0x3e691a4 | +[LTKeychainStorage verifyEntitlementExistsForAccessGroupID:] → YES |
原因：重签后 keychain-access-groups 变成新证书的 TeamID，App 里写死 KG6GWND6BG.com.lightricks.shared，断言失败 → NSAssert 抛异常 → abort。

## v3 追加（修 Swift fatalError）
崩溃栈：_assertionFailure ← Intelligence/INTStorage.swift:34
fatal 信息："Invalid app group passed to UserDefaults(suiteName:): "
做法：把二进制里 12 处 `group.com.lightricks` 改成 `groop.com.lightricks`（等长改写）。
原理：UserDefaults(suiteName:) 只在 group. 前缀且无授权时返回 nil；改前缀后变成普通 suite，
非 nil，fatalError 不再触发；同时 App Group 相关 entitlement 校验也随之失效。

## v4 追加
| 0x103b8b7ac | 0x3b8b7ac | INTStorage: `cbz w19` (UserDefaults(suiteName:) 为 nil 的分支) → nop |
即使 app group 名字被改写成 groop.*，该处仍走到 fatal 分支，直接把这条分支砍掉；
x19=nil 时后续全部是 ObjC 消息发送，nil 安全，不会崩。
