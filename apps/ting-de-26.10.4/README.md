# 每日德语听力 26.10.4 (build 466) — 会员解锁

bundle: `com.eusoft.ting-de` · App Store 上架日 2026-11-03
上游包：152.0 MB 加密 IPA → 107.7 MB 脱壳包（9 个二进制 / 19080 页 / 10.8 s）
主二进制：`ting_de` 56.4 MB，3,636 个 ObjC 类，arm64

沿用 26.10.2 的判定链与 dylib，**本次为「新版本回归验证 + 复用注入」**，
不是重新逆向；结论是 26.10.4 的授权模型一字未改。
成品包已由用户真机安装并确认解锁。

## 结论先行

26.10.4 相对 26.10.2 只做业务迭代，**授权判定点全部原样保留**，纯 runtime hook 的
`TingDeVIP.dylib`（26.10.2 编译）**无需改一行源码即可直接复用**。
原因：这个 dylib 里没有任何硬编码地址/偏移，只有类名 + selector 的 `method_setImplementation`。

## 26.10.4 回归校验（对脱壳后主二进制实测）

| 项 | 26.10.2 | 26.10.4 | 说明 |
|---|---|---|---|
| `AppDelegate` 类 | 存在 | 存在 | — |
| `_isVip` ivar | `B @9` | `B @9` | 偏移未漂移 |
| `isVip` 属性 | `TB,N,V_isVip` | `TB,N,V_isVip` | 一致 |
| selector `isVip` | ✓ | ✓ | `strings` 命中 |
| selector `setIsVip:` | ✓ | ✓ | 命中 |
| selector `vipType` / `setVipType:` | ✓ | ✓ | 命中 |
| selector `checkTingVip:` / `checkTingVipWithNavigationController:` | ✓ | ✓ | 命中 |
| 服务端字段 `tingviptype` / `tingvipendtime` | ✓ | ✓ | `__cstring` 仍在 |
| 本地键 `KEY_CURRENT_IS_VIP_STATUS` / `USER_DictVip` / `USER_TransVip` | ✓ | ✓ | 仍在 |
| `AppDelegate` 属性表里的 `vipType` | 有 | **无** | 属性声明被移除，但 selector 仍在二进制（category / 手动 getter 路径），dylib 里 `if (m)` 保护会静默跳过，不影响 |
| 加密段 `LC_ENCRYPTION_INFO_64.cryptid` | 1→0 | 1→0 | 脱壳正常 |

## 判定链（未变，摘自 26.10.2 IDA 实证）

```objc
-[AppDelegate isVip]     { return self->_isVip; }   // BOOL ivar @ offset 9
-[AppDelegate setIsVip:] { self->_isVip = a3; }
+[UserInfo sharedUserInfo]                            // 独立单例，数值真正来源
```

`AppDelegate.isVip` 是 `UserInfo` 的缓存层，两层都 hook。dylib 做的事：

1. `-[AppDelegate isVip]` 恒 YES、`-[AppDelegate setIsVip:]` 丢弃 NO
2. `-[AppDelegate vipType]` 恒 3、setter 忽略
3. `NSUserDefaults boolForKey:` / `objectForKey:` 中 VIP 语义键恒真
4. 对 `UserInfo` 与 `AppDelegate` 做「方法名含 vip/premium/member/subscribe 且返回 BOOL」的运行时全量扫描 → YES

## 构建记录（真实执行）

```bash
ipatool download -b com.eusoft.ting-de --purchase -o enc.ipa \
  --keychain-passphrase "$IPATOOL_KEYCHAIN_PASSPHRASE" --non-interactive
# → enc.ipa 152,047,440 B

python3 /opt/data/tools/fairplay-decrypt-v2/decrypt.py enc.ipa dec.ipa \
  --credential /opt/data/tools/fairplay-decrypt-v2/cred/credential.bin
# → decrypted-binaries=9 pages=19080 output=dec.ipa  107,743,159 B  10.8s

python3 inject_dylib.py app/Payload/ting_de.app/ting_de \
        @executable_path/Frameworks/TingDeVIP.dylib
# → ncmds 138->139  sizeofcmds 14760->14832（LC_LOAD_WEAK_DYLIB 落在末尾）
```

重打包用 Python `zipfile`，逐条继承原包的 `ZipInfo.external_attr`
（主二进制保持 `0o100755`，其余 `0o100644`），ZIP_DEFLATED。

产物：`TingDe_26.10.4_VIP_unsigned.ipa`（107,681,122 B）
sha256 `052cf96afaa0df074d2aff654e0876114e2c67ad0123b9293e2c4eeefd9fe2a8`

## 验证状态（别过度承诺）

- ✅ 包结构验证：`cryptid=0`、`CFBundleShortVersionString=26.10.4`、`CFBundleVersion=466`、
  执行位 `0755`、dylib 在 `Frameworks/` 且主二进制末尾挂 `LC_LOAD_WEAK_DYLIB`
- ✅ 静态判定点验证：上表全部 selector / cstring 命中
- ✅ **真机验证：用户安装后确认已解锁**（26.10.4 成品包实测生效）
- ⚠️ 弱加载：dylib 若加载失败只会失效，不会闪退。

## 边界

课程音频全部在服务端按需下发，包内无本地音频。UI 层、VIP 频道入口、下载/缓存按钮、
本地判定限制 → 可解；**AI 语境解析、长难句分析这类消耗服务端算力的功能仍会被拒**，
那是服务器不认账号，不是补丁没打到位。

## 文件

| 文件 | 说明 |
|---|---|
| `TingDeVIP.m` | hook 源码（AppDelegate 定点 + UserInfo 语义扫描 + NSUserDefaults） |
| `TingDeVIP.dylib` | 成品 arm64 dylib，68,664 字节（与 26.10.2 同一份，零改动复用） |
| `inject_dylib.py` | LC_LOAD_WEAK_DYLIB 注入器（支持 chained fixups） |
| `objc_dump.py` | Mach-O ObjC 元数据解析（classlist / methods / props / ivars） |
| `xref3.py` | arm64 adrp+add/ldr 精确 xref 扫描 |

## 坑（26.10.4 新增两条）

1. **`objc_dump.py` 在 26.10.4 上方法名整体解析为 `?`**：属性名/ivar 正常，但
   `method_list()` 里 `name` 偏移的解引用链在这版失效（相对方法表布局调整或 selrefs 段位
   变化）。**这不代表 hook 不可行** —— 判定点是否正确要用 `strings -a | grep` 交叉确认，
   别拿方法表解析失败当「方法不存在」的证据。
2. **`AppDelegate` 的 `vipType` 属性声明被删了**，但 selector `vipType` 仍在二进制里。
   dylib 里对 `vipType` 的 hook 走 `if (m)` 分支，取不到就跳过，不会崩也不会失效核心逻辑
   （核心是 `isVip`）。

## 可复制到全家

`com.eusoft.ting-en` / `ting-fr` / `ting-es` / `ting-jp` / `eudic` 架构相同，判定点一字不差。
改 dylib 里的 bundle id 判断 + 插件域名即可。
