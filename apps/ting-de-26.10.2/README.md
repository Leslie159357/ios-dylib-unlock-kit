# 每日德语听力 26.10.2 (build 463) — 会员解锁存档

bundle: `com.eusoft.ting-de` · 产物: `/opt/data/downloads/TingDe_26.10.2_VIP_v2.ipa` (102.7 MB)
实测结果：用户真机确认已解锁。

## 判定链（IDA 伪代码实证）

```objc
-[AppDelegate isVip]     { return self->_isVip; }   // BOOL ivar @ offset 9
-[AppDelegate setIsVip:] { self->_isVip = a3; }
+[UserInfo sharedUserInfo]                            // 独立单例，数值真正来源
```

`AppDelegate.isVip` 是 `UserInfo` 的缓存层，**两层都要 hook**。

服务端字段（`__cstring` 相邻常量取证）：

| 字段 | 值域 |
|---|---|
| `tingviptype` | `forevervip` / `multiyearvip` / `annualfeevip` |
| `tingvipendtime` | 到期时间字符串 |

本地键：`KEY_CURRENT_IS_VIP_STATUS`、`Key_User_Info`、`USER_DictVip`、`USER_TransVip_EndTime`
接口：`https://api.frdic.com/api/v2/auth/UserInfo`（无 token → 401）
判定入口：`-[? checkTingVip:]`、`-[? checkTingVipWithNavigationController:]`

## 复现

```bash
# 1. 下载（ipatool 已登录态）
ipatool download -b com.eusoft.ting-de --purchase -o enc.ipa \
  --keychain-passphrase "$IPATOOL_KEYCHAIN_PASSPHRASE" --non-interactive

# 2. 脱壳（152 MB → 108 MB，9 个二进制 / 19048 页，< 1 分钟）
python3 /opt/data/tools/fairplay-decrypt-v2/decrypt.py enc.ipa dec.ipa \
  --credential /opt/data/tools/fairplay-decrypt-v2/cred/credential.bin

# 3. 解包 + 注入 + 重打包
unzip -q dec.ipa -d app
cp TingDeVIP.dylib app/Payload/ting_de.app/Frameworks/
python3 inject_dylib.py app/Payload/ting_de.app/ting_de \
        @executable_path/Frameworks/TingDeVIP.dylib
# zip 只打进 Payload/ 下 1280 个文件
```

## 文件

| 文件 | 说明 |
|---|---|
| `TingDeVIP.m` | hook 源码（AppDelegate.isVip / vipType / NSUserDefaults + UserInfo 运行时全量扫描） |
| `TingDeVIP.dylib` | 成品 arm64 dylib，68,664 字节 |
| `inject_dylib.py` | LC_LOAD_WEAK_DYLIB 注入器（支持 chained fixups 二进制） |
| `objc_dump.py` | Mach-O ObjC 元数据解析（classlist / methods / props / ivars） |
| `xref3.py` | arm64 adrp+add/ldr 精确 xref 扫描 |

Loon 插件：`/opt/data/loon-plugin/plugins/TingDe/tingde.plugin`
（改写 `UserInfo` 响应，递归扫 key，不硬编码 JSON 结构）

## 坑

1. **主二进制 56 MB，IDA 全量分析 11 分钟、库 885 MB，二次打开 `open_database failed rc=4`**（内存不足）。
   查单个函数优先用 `objc_dump.py`，不要反复开 IDA 库。
2. chained fixup 指针：`raw & 0xFFFFFFFFF` 是 vmoffset，但 `class_ro_t` 里的指针可能是**明文
   vmaddr**，判定要收紧到 `IMAGE_BASE <= raw < IMAGE_BASE + 0x4000000`，否则误判成巨大偏移。
3. `__objc_selrefs` 条目是 rebase 到 `__objc_methname`，方法名要**二次解引用**才拿到字符串。
4. arm64 `adrp` 的字节 mask 是 `(w & 0x9F000000) == 0x90000000`，
   若把 Rd 位一起 mask 进去（`0x9F00001F`）会漏掉除 x0 外的全部 adrp。
5. **课程音频全部在服务端**，包内无本地音频。AI 语境解析 / 长难句分析走服务端算力，
   本地补丁无论多完整都会被拒——这不是破解不到位。

## 可复制到全家

`com.eusoft.ting-en` / `ting-fr` / `ting-es` / `ting-jp` / `eudic` 架构相同，
判定点一字不差。改 dylib 里的 bundle id 判断 + 插件域名即可。
