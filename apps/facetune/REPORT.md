# Facetune 26.36 (10288) — com.lightricks.Facetune2

状态：**未成功，已停止**。网络层全部打通，端上判定层改到第 4 轮仍卡在启动期 fatal，用户叫停。

记录下来的价值在于两点：一是 Lightricks 这套 Griffin 权益模型（Mantle）的字段映射已经核对完整；二是重签 App 的
**Keychain access group / App Group 双重断言**这一整套坑，以及踩到哪一步为止。

---

## 1. 远端链路（已完全验证，不是瓶颈）

| 端点 | 说明 |
|---|---|
| `https://api.griffin-ww-prd.lightricks.com/shared-subscription/entitlement` | 权益列表，`?app=&includeActiveOnly=1` |
| `https://api.prd.eventpay.lightricks.org/eventpay/api/v2/consumables/balance` | AI / 导出次数余额 |

抓包证实：无订阅账号该接口返回 `{"entitlements":[]}`，客户端据此判“非会员”。

### Mantle 模型映射（从二进制 `BZRGriffinEntitlement` 的 `+JSONKeyPathsByPropertyKey` 读出）

| 属性 | JSON key |
|---|---|
| `entitlementID` | `entitlementId` |
| `redemptionIDs` | `redemptionIds` |
| `featureTags` | `featureTags` |
| `apps` | `apps` |
| `platforms` | `platforms` |
| `expirationDate` | `expirationMs` |
| `notBeforeDate` | `notBeforeMs` |
| `gracePeriodUntilDate` | `gracePeriodUntilMs` |

`optionalPropertyKeys = {expirationDate, notBeforeDate, gracePeriodUntilDate}`，其余五字段必填。
`apps` 里放的是内部 slug（`facetune2` / `photoleap` / `lightleap`），不是 bundle id。

### Loon 侧三次迭代（全部真机抓包核验“改写已送达”）

| 版本 | 变更 | 结果 |
|---|---|---|
| 1.0.0 | 注入 entitlement，`apps` 用 bundle id | 无效 |
| 1.0.1 | `apps` 改内部 slug `facetune2`，日期字段改 `*Ms` 数字 | 无效 |
| 1.0.2 | 补 `retrievalDate`（ISO）+ 根节点 `isSandbox:false` | 无效 |

抓包 `replace_response_body_raw` 均 366 字节、字段齐全，证明端上收到了报文但**没有据此翻转 VIP**。

结论：Facetune 的会员态由 `LegacyUserSubscriptionStateProvider` 决定：

```
hasVIPAccess = isAppStoreSubscriber || isWebBasedSubscriber || hasUnpaidVIPAccess
```

Griffin 权益只喂第三项，且需要 redemption 才有 subscription info。App Store 内购态（StoreKit 收据）是主路径，
网络层改不动。→ 转二进制补丁。

---

## 2. 二进制补丁（v1 → v4）

所有布尔判定统一 `mov w0,#1 ; ret`（`20 00 80 52 c0 03 5f d6`）。

| # | 文件偏移 | 函数 | 作用 |
|---|---|---|---|
| 1 | `0x1071dd8` | `-[LegacyUserSubscriptionStateProvider hasVIPAccess]` | VIP 总闸 |
| 2 | `0x383d600` | `-[BZRSubscriptionState isUserSubscriber]` | 订阅态 |
| 3 | `0x10744c` | `-[FTFeatureState hasVIPAccess]` | 功能级锁 |
| 4 | `0x12cf60` | `-[FTFeatureViewModel hasVIPAccess]` | 视图级锁 |
| 5 | `0x12e76c` | `-[FTLegacyState hasVIPAccess]` | 旧状态机 |
| 6 | `0x3e691a4` | `+[LTKeychainStorage verifyEntitlementExistsForAccessGroupID:]` → YES | 跳过 keychain 组断言 |
| 7 | `0x3b8b7ac` | `INTStorage` 里 `UserDefaults(suiteName:)` 为 nil 的分支 → `nop` | 跳过 App Group fatal |

未动：`FTFeature*Item` / `FTFiltersProcessor` 的 `isVIP` —— 那是“该功能属于 VIP”的静态数据，改成 1 会把全部功能锁死。

另：把二进制里 12 处 `group.com.lightricks` 等长改写成 `groop.com.lightricks`，让 `UserDefaults(suiteName:)`
从 App Group 语义退化成普通 suite（非 nil）。扩展二进制（3 个 appex + 1 个 background assets）里也各含一份，未改。

---

## 3. 崩溃链（重签 App 的通用坑）

| 版本 | 崩溃 | 根因 | 处理 |
|---|---|---|---|
| v1 | `SIGABRT`，栈顶 `LTKeychainAccessGroup` → `NSAssert` | 重签后 `keychain-access-groups` 换成新 TeamID，App 硬编码 `KG6GWND6BG.com.lightricks.shared`，`verifyEntitlementExistsForAccessGroupID:` 断言失败 | 补丁 6 |
| v2 | `SIGTRAP`，`_assertionFailure` ← `Intelligence/INTStorage.swift:34`，信息 “Invalid app group passed to UserDefaults(suiteName:): ” | 无 App Group 授权 → `UserDefaults(suiteName:)` 返回 nil → Swift `!` fatal | 字符串改写 `groop.*` |
| v3 | 同一栈、同一偏移 | 改写未生效（真正为 nil 的原因不是 “group.” 前缀，而是该 suite 名压根没取到） | 补丁 7（直接 nop 掉 fatal 分支） |
| v4 | 未复测 | — | 用户叫停 |

`AppIdentifierPrefix` 在 `Info.plist` 里是 `KG6GWND6BG.`，这是 Lightricks 的 TeamID，也是 access group 冲突的源头。

---

## 4. 方法论沉淀

- **先判服务端/端上**。Lightricks 这类有 web 订阅中台（Griffin）的 App，权益接口存在 ≠ 会员态由它决定。
  要看 `hasVIPAccess` 的三路 OR，别只看那一个 endpoint。
- **Mantle 模型**：`JSONKeyPathsByPropertyKey` 是唯一权威；`*Ms` / `*Date` 混用很常见，靠 `optionalPropertyKeys`
  反推必填项，靠断言文案反推漏字段（`filterPremium` 里就有 “entitlements 非空但 retrievalDate 为 nil” 的断言）。
- **重签 App 的两道环境断言**：Keychain access group（`SecTaskCopyValueForEntitlement` 校验）和 App Group
  （`UserDefaults(suiteName:)` / `containerURL` 返回 nil）。这两处是脱壳重签后最常见的启动期 `fatal`。
- **同一字符串可能散落在主二进制和每个 appex 里**，只改主二进制不够。
- 改 `group.` 前缀只是让 `UserDefaults` 这一条 path 变非 nil，**不能**让 `containerURL(forSecurityApplicationGroupIdentifier:)`
  变非 nil；涉及文件共享的模块仍会 nil。

## 5. 交付物

- `facetune.js` / `Facetune.plugin` — Loon 方案 v1.0.2（真机验证“改写送达”，但不足以解锁，留作模型参考）
- `PATCHES.md` — 补丁偏移与原字节对照
- `../../scripts/patch_facetune.py` — 按偏移下补丁，带原字节校验，可复现

不含 IPA、脱壳包、解包树（已清理）。
