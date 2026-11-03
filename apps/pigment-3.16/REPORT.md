# Pigment 3.16（com.pixite.pigment）— RevenueCat + 本地到期日的“无网门”结构（2026-10-28）

## 判定链（IDA 9.4 实测）

- `-[SubscriptionManager checkIsPremium]` = `isGrandfatheredPremiumStatus` 或 `latestPremiumExpirationDate > now`；命中走 `setIsPremium:YES` + `premiumAccessEnabled`，否则 `setIsPremium:NO` + `premiumAccessDisabled`。
- 到期日不是网络实时计算：`RevenueCatSubscriptionHelper.applyPremiumAccess(from:restoringOnStaleCache:)` 从 `NSUserDefaults` 读 `premium_expiration_date` / `pig_premium_expiration_date`，未来则把 Swift ivar `isPremiumAccess` 置真；过期则 `removeObjectForKey:` 并 `restorePurchases`。
- 版本信息：3.16 (880)，iOS 16+，主二进制 25MB，RevenueCat 5.83.1，Superwall 付费墙仅 UI。

## 为什么没有 Loon 面

- `api2.pigmentapp.co` 只有 `remote_config/config.json`（订阅 family id、后缀等配置）。
- `api3.pigmentapp.co/content` 是 Elasticsearch 内容网关（凭据内置，无凭据 401），只发内容不发权益；assets 静态域名不带签名。
- 全应用不存在“我的订阅状态”响应体；RC 5.83.1 带 `signature_*` 校验字段。结论：直接注入，别硬写 Loon。

## 注入设计（纯 C，零 SDK 可编译）

1. `SubscriptionManager`：`checkIsPremium` swizzle 后追加 `setIsPremium:YES`；`isPremium` → YES；`isGrandfatheredPremiumStatus` → YES；`latestPremiumExpirationDate` → `+10y`。
2. `_TtC15PixiteSubscribe28RevenueCatSubscriptionHelper`（Swift 类，经 `@objc protocol PremiumChecker` 暴露，`isPremiumAccess` 走 objc_msgSend 可 Hook）：`isPremiumAccess` → YES；`latestPremiumExpirationDate` → `+10y`。
3. constructor 只起 pthread，睡 1.5s 后往 UserDefaults 写两个到期日键为 10 年后，让官方逻辑自己算出订阅态（该层即使 Hook 全失效也大概率生效）。

## 红线与核对

- **v1 真机闪退教训（2026-10-28）**：worker 线程里第一次 `objc_msgSend` + `+[NSString stringWithUTF8String:]` 就 `EXC_BAD_ACCESS`，ips 的 subtype 写着 `possible pointer authentication failure`，帧序为 `_platform_strlen ← +[NSString stringWithUTF8String:] ← PigmentUnlock.dylib worker`。arm64 交叉编译的 dylib 在 arm64e 进程里调通用 `objc_msgSend`（尤其带 variadic 声明）会命中 PAC 陷阱，**不是**写偏好太早的问题。修法：dylib 内零 `objc_msgSend`、零 Foundation——写偏好改 `CFPreferencesSetAppValue` + `CFSTR` 字面量，返回日期用 toll-free bridged `CFDateCreate`，让 `checkIsPremium` 自己拿改过的 `latestPremiumExpirationDate` 去算。
- `isPremium` 在 Book/Page/ASMPalette 上是“此内容需付费”，置真会锁内容。只对类名含 `Subscription/Subscribe/Purchase/UserManager/Profile/Account/Session/StoreKit/PremiumChecker` 的类改 `isPremium`；`isPremiumAccess` / `hasPremiumAccess` 语义唯一，可对所有类安全改写。
- Swift 类无导出符号：`ida_scan.py --list-only "RevenueCatSubscriptionHelper"` 能看到 `-[_TtC... isPremiumAccess]` 就证明 ObjC 可见、Hook 有效；看不到才需要静态微补丁。
