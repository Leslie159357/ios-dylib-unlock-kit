# OhMyCity — Pro 解锁（端上判定，二进制补丁）

- App：OhMyCity 1.1.3（CFBundleVersion 27）
- Bundle ID：`com.7mlstudio.ohmycity`
- 主二进制：arm64，6,095,920 字节，SwiftUI + StoreKit 2
- SHA256：`28195d87c4ee77e04e7d097c0d98b418a4a5850310b34c2df1b0fb3bacaa2233`
- 结论：**判定全在端上，网络层没有可改写的字段**。补丁 6 条 4 字节指令即全解锁。

---

## 1. 先判：能不能走 Loon

用户提供的抓包（9 条请求）全部是 App 内置 SFSafariViewController 打开的官网活动页：

| 请求 | 类型 |
|---|---|
| `/zh/event/` | HTML（分享领会员活动页） |
| `/style.css` `/showcase.css` `/event.css` | 静态样式 |
| `/assets/fonts/nunito.ttf` | 字体 |
| `/assets/brand/logo.png` | 图标 |
| `/cdn-cgi/rum?` ×2 | Cloudflare RUM 上报 |
| `static.cloudflareinsights.com/beacon.min.js` | CF 统计 |

全部 `cf-cache-status: HIT`，无任何会员/订阅相关接口。

二进制侧的旁证：主二进制里出现的唯一业务域名是 `https://ohmycity.7mlstudio.com/content/`（内容清单，配套 `com.7mlstudio.ohmycity.content-attest` 做 App Attest），没有任何 `is_pro` / `isPremium` 之类的回包字段。会员状态来自：

```
StoreKit 2  →  Transaction.currentEntitlements  →  本地 JWS 验签  →  PurchaseStore.isPro
```

JWS 由 Apple 私钥签发，端上伪造不了；网络层也没有承载它的报文。**这类 App 不存在 Loon 方案**，任何"改写响应体"都是在改不存在的东西。

## 2. 判定链

`PurchaseStore` 是 `@Observable` 类，从 `__objc_ivar` 可读出布局：

| ivar | 偏移 | 语义 |
|---|---|---|
| `_isPro` | 0x10 | Bool，会员总开关 |
| `_isLoaded` | 0x11 | Bool，entitlements 是否已解析 |
| `_entitlementResolution` | 0x12 | 枚举，解析结果（0/1/2，构造时默认 3 = 进行中） |
| `_products` | 0x18 | 商品数组 |
| `_selectedPlan` | 0x20 | `ProPlan?`，购买页选中项 |
| `_activePlan` | 0x21 | `ProPlan?`，当前生效档位 |

`ProPlan` 枚举（由 `ProPlan.hash(into:)` 的 CSEL 链反推）：

```
0 = lifetime   1 = yearly   2 = monthly
```

`_activePlan` 是 `Optional<ProPlan>`，单字节编码 `0 = nil, 1 = .lifetime, 2 = .yearly, 3 = .monthly`（setter 里有 `CMP W8,#3` 的分支，坐实 3 是上限）。

`PurchaseEntitlements`（值类型，在 refresh 协程里 allocBox 构造）：

```
byte0 = isPro
byte1 = isLoaded
byte2 = resolution   (构造时写 3)
...
```

构造点：

```
sub_1000E3E30:
    MOV  W8, #0x100
    STRH W8, [X27]        ; byte0=0(isPro=false), byte1=1(loaded)
    MOV  W8, #3
    STRB W8, [X27,#2]     ; resolution=3
    BL   static Transaction.currentEntitlements.getter
    ...遍历 → 逐条验签 → 填结构体
```

应用点 `PurchaseStore.apply(_:)`（`sub_1000E9198`）：

```
LDRB W20,[X25]          ; 新结构体 byte0 = isPro
LDRB W8, [X19,#0x10]    ; 当前 store.isPro
CMP  W20, W8
B.EQ skip
... ObservationRegistrar.withMutation(of: keyPath(qword_10040BD30), _)
```

## 3. 第一版为什么白干（重要方法论）

第一版只改了 `isPro` 的 getter 和 setter（`sub_1000D9190` / `sub_1000E4C08`），装上去毫无变化。原因：

1. **读被内联**：同模块 full-module 优化下，SwiftUI 视图读 `store.isPro` 直接编译成 `LDRB W?, [store,#0x10]`，根本不 `bl` getter。
2. **写绕开 setter**：`apply(_:)` 不是调用 setter，而是走 `ObservationRegistrar.withMutation(of:keyPath:_:)` + 闭包，闭包体里直接 `STRB W9,[X8,#0x10]`。setter 函数只在少数路径被调用。

**教训：`@Observable` 类型的属性，getter/setter 不是判定锚点。要么改状态写入的源头（结构体默认值 / apply 的读取点），要么改每个内联读点（不可行）。**

## 4. 最终补丁

| 地址 | 原指令 | 改为 | 作用 |
|---|---|---|---|
| `0x1000E3EFC` | `mov w8,#0x100` | `mov w8,#0x101` | 结构体默认 isPro=1 |
| `0x1000E928C` | `ldrb w20,[x25]` | `mov w20,#1` | apply 强制 isPro=1 |
| `0x1000D91FC` | `ldrb w0,[x19,#0x10]` | `mov w0,#1` | getter 兜底 |
| `0x1000DDE00` | `ldrb w0,[x19,#0x21]` | `mov w0,#1` | activePlan → some(.lifetime) |
| `0x1000E4C20` | `and w22,w0,#1` | `mov w22,#1` | setter 兜底 |
| `0x1000E52D8` | `and w22,w0,#0xff` | `mov w22,#1` | activePlan setter 兜底 |

全部 4 字节等长替换，只改 14 个字节（其余字节恰好相同），Mach-O 结构不动。

`patch_ohmycity.py` 会逐条校验「原指令 == 预期值」，输入哈希不符会先警告，任何一条校验失败即中止，不会盲打。

## 5. 复现

```bash
# 1. 取包并脱壳（Linux 侧纯 Python，需要同账号 16 字节 credential）
ipatool download -b com.7mlstudio.ohmycity -o omc.ipa --purchase
python3 /opt/data/tools/fairplay-decrypt-v2/decrypt.py omc.ipa omc_dec.ipa \
        --credential /opt/data/tools/fairplay-decrypt-v2/cred/credential.bin

# 2. 打补丁
python3 patch_ohmycity.py Payload/ohmycity.app/ohmycity ohmycity.p

# 3. 重打包（主二进制 755，剔除 _CodeSignature / SC_Info）
```

产物：`OhMyCity_1.1.3_PRO_unsigned_v2.ipa`（120.6 MB，未签名，自行签）。

## 6. 验证与排查

App 没有在包内显示版本号的地方，所以重打包时把 `CFBundleDisplayName` 改成 `ohmycity ✓`、`CFBundleVersion` 改成 `127`，用来确认装的是补丁包而不是 App Store 原包——**这是这类"装完看不出区别"的补丁必做的一步**。

判据：

- 桌面图标名带 `✓` → 装的是补丁包
- 设置页 PRO 卡片消失 / iCloud 同步开关可用 → 补丁命中
- 图标名没变 → 旧包没覆盖掉，先卸载再装

## 7. 下次遇到同类，按这个顺序找

1. `strings -a` 找 `StoreKit` / `currentEntitlements` / `isPro`，先判端上还是服务端。
2. `__objc_ivar` 符号 `_OBJC_IVAR_$__TtC<模块><类>._isPro` 拿到字段偏移（这里 0x10）。
3. 反查该偏移的 `STRB`/`LDRB` 得到 getter / setter——**但不要停在这里**。
4. 找 `ObservationRegistrar.withMutation` 的闭包（`LDR X8,[ctx,#0x10]; LDRB W9,[ctx,#0x18]; STRB W9,[X8,#off]`），它的调用者就是真正的写入点（这里是 `apply(_:)`）。
5. 再往上找 `Transaction.currentEntitlements` 的唯一调用点，那里构造的 `XxxEntitlements` 结构体默认值也值得改一条（兜底：无交易时保持 true）。
