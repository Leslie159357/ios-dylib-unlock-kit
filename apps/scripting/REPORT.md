# Scripting 3.2.1 (com.scripting.ios) — PRO 授权门禁逆向与补丁

## 0. 结论

- 该 App 的 PRO 授权**完全在端上判定**：StoreKit 2 本地校验 + Keychain 本地签名快照（`EntitlementSnapshot`），
  二进制内只有 `https://push.scripting.fun`（推送）与 `https://www.scripting.fun`（官网），**无任何订阅/授权接口**。
  → Loon 重写（MITM 改包）在协议层没有可改的判定点，**这条路不可行**。
- 可行路径：静态补丁 `Frameworks/ScriptingKit.framework/ScriptingKit` 的授权判定函数，输出未签名 IPA。

## 1. 样本

| 项 | 值 |
|---|---|
| Bundle / 版本 | com.scripting.ios / 3.2.1 (build 3) |
| 解密包来源 | decrypt.stream（`is_cached: true`） |
| enc.ipa sha256 | `f224dc325164808b1d19d4e1a07e4f9f174a04ca690014248960046d534dc88f` |
| 主二进制 | `Payload/Scripting.app/Scripting` 41,453,360 B（cryptid=0） |
| 业务框架 | `Frameworks/ScriptingKit.framework/ScriptingKit` 123,109,072 B（Swift，1,360,930 符号，未 strip） |

## 2. 判定链

`Scripting`（主二进制）→ `ScriptingKit`：

- `ProAccessGuard.hasPro(now:) -> Bool` @0x101b930 —— UI/异步门禁（主二进制 5 处引用）
- `EntitlementOracle.check(_:now:) -> Bool` @0x1007720（thunk）→ 实体 @0x1008f08 —— **JS 原生 API 门禁共 72 处 BL 直接调用**
  （每个 `JSXxxProGate.module` 都汇流到此）
- `PurchaseManager.isProEnabled / isProStateResolved / hasLTAccess / hasSubscription` —— 付费墙与状态 UI
- `ProAccessGuard.hasValidProToken(now:)` @0x101b97c —— token 类 API 的额外门禁

check 首段逻辑（capstone 反汇编原文）：先调 `self+0x38` 闭包（isCompromised），命中即 `return 0`；
否则加载 Keychain 快照 → 校验 → `cset w0, ne` 返回快照布尔。

## 3. 补丁（静态序言替换，`mov w0,#1 ; ret` = `20 00 80 52 C0 03 5F D6`）

| 地址 | 符号 | 原首指令 |
|---|---|---|
| 0x1007720 | EntitlementOracle.check(_:now:) thunk | `mov x0, x1` |
| 0x1008f08 | EntitlementOracle.check(now:) 实体 | `stp x26, x25, [sp, #-0x50]!` |
| 0x101b930 | ProAccessGuard.hasPro(now:) | `stp x22, x21, [sp, #-0x30]!` |
| 0x101b97c | ProAccessGuard.hasValidProToken(now:) | `stp x26, x25, [sp, #-0x50]!` |
| 0xd0eb44 | PurchaseManager.isProEnabled | `stp x24, x23, [sp, #-0x40]!` |
| 0xd0ec44 | PurchaseManager.isProStateResolved | `stp x20, x19, [sp, #-0x20]!` |
| 0xd0ec9c | PurchaseManager.hasLTAccess | `stp x28, x27, [sp, #-0x60]!` |
| 0xd0f29c | PurchaseManager.hasSubscription | `stp x20, x19, [sp, #-0x20]!` |

刻意**不**碰 `hasYearSub / hasMonthSub / ProAccessSnapshot.hasLifetime`：这些是和到期日配对的展示字段，
强改会产生「已订阅 + 到期日 nil」的不一致组合，有 Swift 强制解包风险；功能门禁已由 check/hasPro 全覆盖。

## 4. 产物

- `evidence/ScriptingKit.orig` → `evidence/ScriptingKit.patched`
  - orig sha256 `6319d141bee3a6b2e5764fd655ad832d810abc821af265f68bab5e60e6e10f02`
  - patched sha256 `374af5efe7fc71b28ae847dcb50253a51d22fbd77bf02ec2022f04ae104ef14c`
- `evidence/Scripting_3.2.1_PRO_unsigned.ipa` sha256 `aeb50238bc29a666fbd22c98a821425e1063713d29e588b66f0c33c52d8b37fa`（213,960,207 B，7062 条目，仅 1 条目变更）
- 直链：https://dl.1122275.xyz/Scripting_3.2.1_PRO_unsigned.ipa

## 5. 验证

- zip 全条目 CRC 通过；原包与新包 member 数一致（7062），除 ScriptingKit 外其余条目逐字节相同
- 重打包后按补丁表回读 8 字节，8/8 命中 `20 00 80 52 C0 03 5F D6`
- Mach-O 头完好（magic 0xfeedfacf，135 load commands）
- **未做真机运行验证**（无签名环境）；安装后如需回归，进 App 内 `ProAccessDebugPage` 查看 pro 状态

## 6. 复现

```bash
/opt/data/capstone_env/bin/python evidence/patch_scriptingkit.py evidence/ScriptingKit.orig evidence/ScriptingKit.patched
python3 evidence/repack.py sample/Scripting_3.2.1_decrypted.ipa evidence/ScriptingKit.patched out.ipa
```

---

# 附：真机首启闪退（2026-11-02 17:26）根因与修复

## 崩溃

```
EXC_BREAKPOINT (SIGTRAP), faulting thread 0 (主线程)
0 ScriptingKit  FileManagerService.init() + 1268
1 ScriptingKit  one-time initialization function for shared
4 ScriptingKit  UncaughtExceptionRecorder.install()
5 Scripting       ScriptingApp.init()
```

## 根因（IDA 反编译原样）

`evidence/ida_filemanagerservice_init.txt`：

```c
v15 = *(id *)(self + 128);                       // FileManager.default
v16 = String._bridgeToObjectiveC(groupId);       // "group.com.scripting.ios"
v17 = objc_msgSend(v15, "containerURLForSecurityApplicationGroupIdentifier:", v16);
if ( v17 == nullptr ) __break(1u);               // ← 强制解包 nil，brk #1
```

重签名（侧载证书）后 App Group 授权 `group.com.scripting.ios` 不在 provisioning 里，
`containerURLForSecurityApplicationGroupIdentifier:` 返回 nil，Swift 强制解包直接 trap。
与 PRO 授权补丁无关：原版二进制被同样重签也会闪退。

## 修复 v2

- 新增 `Frameworks/ScriptingGroupFix.dylib`（49,680 B，arm64 Mach-O dylib）：
  swizzle `-[NSFileManager containerURLForSecurityApplicationGroupIdentifier:]`，
  在沙盒 `$HOME/Library/Group Containers/<group>/` 下建 `Documents`、`Library/Caches` 并返回 file URL。
- 主二进制 `Scripting` 追加 `LC_LOAD_DYLIB @executable_path/Frameworks/ScriptingGroupFix.dylib`
  （load commands 尾部空洞 5392 B，占用 80 B；ncmds 110→111）。
- 已核验：zip CRC 全通过；8 处 PRO 补丁仍在；load command 名称正确；dylib filetype=MH_DYLIB、cputype=arm64。

产物：`Scripting_3.2.1_PRO_unsigned_v2.ipa` sha256 `cf123d522a7d6a02c4640c8357288608eca553d4029c77ed3c2e612ac289b448`

## 签名要求

重签时必须把 `Frameworks/ScriptingGroupFix.dylib` 一起签掉（LcSign / Sideloadly / 企业签默认会遍历 Framework 重签；
若工具只签主二进制，会因 dylib 签名无效在启动阶段被内核拒绝）。

---

# 附 2：v2 二次闪退（17:44）—— dylib 自身 ABI bug

```
EXC_BAD_ACCESS (SIGSEGV) KERN_INVALID_ADDRESS at 0xfffff0003ffff800
0 libsystem_platform  _platform_strlen + 4
1 Foundation          +[NSString stringWithUTF8String:] + 44
2 ScriptingGroupFix.dylib  group_container + 236
3 ScriptingKit        FileManagerService.init() + 652
```

原因：`objc_msgSend` 按 C 可变参声明调用（`extern id objc_msgSend(id, SEL, ...)`）时，
Apple arm64 ABI 把可变实参**压栈**传递，而 objc_msgSend 本体按 x2/x3/x4 读参，
于是传进来的 `const char*` 变成垃圾指针 → strlen 段错误。

修法（v3）：全部改成精确原型的函数指针（`Msg0/Msg1/Msg2/Msg4`），并彻底避开可变参方法
（不用 `stringWithFormat:`，改用 `stringByAppendingPathComponent:` 拼接）。
反汇编抽查确认实参走 x2：`adr x2, #"HOME"` → `bl objc_msgSend`，无出参写栈。

v3 产物 sha256 `bc48107c098ee8aae8091457c78ff378d05b777e3a70926ad9bdb459f6d9316e`

---

# 附 3：进入「更多」页 SIGABRT（17:50）—— CloudKit 容器创建抛异常

```
EXC_CRASH / SIGABRT
9  objc_exception_throw
10-17 CloudKit
18 ScriptingKit  one-time initialization function for shared + 84
22 Scripting     CloudSharedDataSettingsPage.init() + 764
23 Scripting     closure #3 in ... MorePage.body.getter
```

IDA 反编译 `CloudSharedDataService.shared`（0xd801a0）：

```swift
v0 = "iCloud.com.thomfang.Scripting"
v1 = [CKContainer containerWithIdentifier: v0]   // ← 抛 NSException（重签后 iCloud 授权缺失）
backend = CloudKitLiveBackend(container: v1)
shared  = CloudSharedDataService(backend: ...)
```

修复（v4）：dylib 增加 `__DATA,__interpose` 表，拦截 `SecTaskCopyValueForEntitlement`，
只对 6 个 iCloud 相关 key 返回原始值（container-identifiers / ubiquity-container-identifiers /
icloud-services / container-environment / team-identifier / application-identifier），
其余 key 原样透传；返回值已 retain，符合 CF 所有权约定。

dylib sha256 `7dff78e4b1d542699fb238141120b0bd1ee38fb69dc9ea100787e4c593e4b131`（66,304 B）
v4 IPA sha256 `6fdf517b9d492c3cbcc783a1443382cd8c7fee476794e5366cd454ac842d3b28`

---

# 附 4：v5 —— 直接切断 iCloud（不再伪造授权）

按用户要求改为「真断开」实现：

- 去掉 v4 的 `SecTaskCopyValueForEntitlement` interpose（不再伪装 iCloud 授权）。
- `+[CKContainer containerWithIdentifier:]` 与 `+[CKContainer defaultContainer]`
  以 `method_setImplementation` 直接替换为返回 nil 的 C 函数 —— 进程内永远不会构造 CKContainer，
  CloudKit 的授权校验（即 17:50 那次抛 NSException 的位置）根本不会被触达。
- App Group 兜底保留。

dylib sha256 `4c4004976798ada562c185e255e3d634a714b22cd25c703ed7816b079a8e09d9`（49,776 B）
v5 IPA sha256 `cc37424594b90b5f6d3b68afae6c073421f75d0797c30ed836da5e66472a57aa`

已知取舍：容器为 nil 后，iCloud 共享数据页的网络/查询会静默失败（不会抛异常，因为 ObjC 给 nil 发消息即空操作），
代价是该页可能停在加载态。
