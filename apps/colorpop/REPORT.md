# Color Pop AI（com.mwm.procolor / MWM PublishingSDK）解锁实录

2026-10-26 真机验证通过。适用于 MWM 全系（PublishingSDK + LedgerKit + DynamicScreen 三件套）。

## 一、这个架构为什么 Loon 必死（可复用的判定法）

**判定证据（一条日志即可定案）**：解锁前后网络返回完全没变，锁却开了。

```
15:13:58  [Features] No features found for current app / user.
          inventory: {features: {}, subscriptions: [], products: []}
15:14:03  packDetailOpened(... isLocked: false)
```

整个冷启动只连三个域名，没有一个是权益接口：
- `event.mwm-bs.com/procolor-backend/ios/insert`（埋点）
- `fastly.mwm-storage.mwmcdn.com/raw_files/...`（图片 CDN）
- `prod.recommendation.procolor-backend.mwmwebapis.com/categories/list`（分类名，posts 全 null）

结论：**权益 = 本地 StoreKit 交易记录（LedgerKit `refresh_inventory`）**，侧载下 StoreKit 恒定 -1008 → `features:{}`。全程无 HTTP 报文承载解锁标志，Loon 没有可改写对象。

> 判定口诀：`inventory/features` 由 SDK 从收据本地算出、且日志里没有「向某域名问权益」的请求 → 网络层介入概率 0，直接上二进制补丁，别浪费回合写插件。

## 二、为什么 ObjC hook 全都「装了但没用」

```objc
-[FeatureRepository isAnyPremiumFeatureUnlocked]
-[MWMApp isAnyPremiumFeatureUnlocked]
Callers: （空）
```

Swift 内部直接 `bl` 到函数体，不走 `objc_msgSend`。`method_setImplementation` 只改 ObjC 方法表，Swift 路径完全不看它。判断方法：IDA 里 `CodeRefsTo` 该方法地址，调用方为 0 就是铁证。

## 三、三处 4 字节补丁（v2.68.00 实测地址）

| 文件偏移 | 原指令 | 改为 | 函数 |
|---|---|---|---|
| 0x144cf80 | `AND W0,W21,#1` = `0x120002a0` | `MOV W0,#1` = `0x52800020` | `-[FeatureRepository isAnyPremiumFeatureUnlocked]` 尾部 |
| 0x145684c | `AND W0,W20,#1` = `0x12000280` | `MOV W0,#1` = `0x52800020` | `-[MWMApp isAnyPremiumFeatureUnlocked]` 尾部 |
| 0x67cf74 | `BIC W0,W8,W19` = `0x0a330100` | `MOV W0,#0` = `0x52800000` | `MWMPackLockStatusProvider.isLocked(pack:)` |

第三处来源（Swift 纯类无 `@objc` 业务方法的定位法）：
1. 日志特征串 `PackLockProvider init — initial unlockedFeatureIds=` 反查 init；
2. init 里 `_OBJC_IVAR_$__TtC8ColorPop25MWMPackLockStatusProvider.unlockedFeatureIds` → `DataRefsTo` 圈出该类仅有的几个成员函数；
3. 判定函数反编译 = `Set.contains(...)` 后 `(v & 1) == 0`，汇编就是 `MOV W8,#1` + `BIC W0,W8,W19`。

## 四、必须离线打补丁（血泪）

- 运行时 `mprotect` / `mach_vm_protect(VM_PROT_COPY)` 写主二进制 `__TEXT` → 执行到脏页即 `SIGKILL`，`.ips` 记 `termination: {namespace: CODESIGNING, indicator: "Invalid Page", code: 2}`。
- 正解：解包 → 用 Python 校验原 4 字节（不符就跳过）→ 就地替换 → 重新弱加载注入 → 打包，交给端侧重签工具整体重签。
- 改完必须回读断言：`0x67cf74` 应是 `00008052`。

## 五、侧载 StoreKit -1008 → 引导页死循环

`load product error URLError -1008` + `ds3_pl_placement_request_failed failure_reason: in_app_purchases` = 引导页（DynamicScreen placement）强依赖内购商品，侧载永远拿不到。

解法：dylib 后台线程（**300ms 后，绝不能在 constructor 里碰 objc**）写 `MWMOnboardingShown / onboardingCompleted / onboardingShown = YES`，`MWMPublishingSDKIsFirstLaunch / isFirstLaunch = NO`。

## 六、constructor 里碰 objc 必崩（另一条血泪）

```
EXC_BAD_ACCESS (SIGBUS) KERN_PROTECTION_FAILURE at 0x4000000000
libobjc  namedClassTableHash / getClassFromNamedClassTable / look_up_class
ColorPopUnlock.dylib  cpop   ← ctor 里调了 objc_getClass
```

dyld 跑 initializer 时 libobjc 类名表还没建好。构造函数里只能做**纯 libSystem 操作**（`open/write/usleep/mprotect`），一切 `objc_getClass` / `NSUserDefaults` / `dispatch_*` 挪到 `pthread_create` 的线程里，延迟 300ms+ 再跑。

## 七、验证清单（真机）

- `packDetailOpened(... isLocked: false)` ← 之前是 true
- 日志中不再出现 `cpop2DrawingViewToolLockedClicked(lockedBy: .pack)`
- `[Marketplace] PackLockProvider init — initial unlockedFeatureIds=[]` 仍在是正常的（我们改的是判定，不是数据）
- 购买按钮仍会报错：StoreKit -1008 是侧载环境固有，不是新问题

## 八、换版本怎么办

偏移绑定 2.68.00。App 更新后：IDA 重新搜 `PackLockProvider init` 字符串 → init → DataRefsTo ivar → 判定函数 → 重新取 4 字节。三条补丁的判断特征（`AND Wn,Wn,#1` / `BIC W0,W8,Wn`）稳定，偏移会变。


## 本目录产物

- `ColorPopUnlock.dylib`（66,608 B，arm64，纯 C/无 SDK）
- `REPORT.md`：MWM 全系（PublishingSDK + LedgerKit + DynamicScreen）判定链与补丁位

`strings` 实测 hook 目标：`isAnyPremiumFeatureUnlocked`、`isUserPremium`（返回 YES），
并置 onboarding 标志位；与报告里的「LedgerKit 本地收据算权益、无网络面」结论一致。
