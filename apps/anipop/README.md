# 开心消消乐 1.163.235（iOS，com.happyelements.1OSAnimal）Lua 补丁复盘

Cocos2d-x 2 + LuaJIT 的三消网游。业务逻辑全在 `Assets/src` 下 10764 个加密 Lua 里，
主二进制是 `HelloLua`，网络层只影响广告与埋点。

本目录只放结论、补丁脚本与踩坑记录，不含任何 App 本体。

---

## 1. 包结构

```
Payload/HelloLua.app/
  HelloLua                                 56.9 MB，LC_ENCRYPTION_INFO_64 cryptid=1(加密)
  Assets/
    bundleVersion                          94df94862e147b6a93ee7f67ff82f6bb
    static_config.b5303857....xml          10764 条 <file md5 size value> 权威清单
    src/**/<name>.<md5>.lua                加密 Lua，md5 = 加密后整文件 md5
```

- 文件封装的 md5 与文件名一致（逐条校验 12158 → 10764 全部通过），说明清单是内容寻址的。
- `static_config.<32hex>.xml` 文件名里的 hex **不是**内容 md5，是版本标识，改内容后**不要改名**。

## 2. Lua 解密

```
文件 = [16B IV] + AES-128-CBC( zlib.compress(lua) + PKCS#7 pad )
解密 = AES-CBC → 去 pad → zlib.decompress
```

AES key 在本版本是 `e9747d92cc322e7d112e7c3451d7b36a`，1.162.236 与 1.163.235 相同。

**key 的定位方法（不需 IDA）**：密钥是 16 字节随机常量，存在 `__TEXT,__const` 里。
拿一个已知密文，用文件前 16 字节当 IV，对 const 段每 16 字节对齐位置做一次 AES 解密，
判据是明文首字节 `0x78` 且次字节 ∈ {0x01,0x5e,0x9c,0xda}（zlib 头）。一次扫 1.3 MB 约 2 秒，
再把命中项逐个跑全量解压即可排除误报。

## 3. 免鉴权配置中心（这次最值钱的发现）

```
GET https://animalmobile.happyelements.cn/config?name=maintenance
```

- 无需登录、无需签名，返回 297 KB / **1309 条 `<maintenance>` 功能闸**，`appName="animal_vpc_mobile_prod0"`，
  其中 41 条带 `platform="apple"`，是 iOS 启动时拉的那份 A/B 分层表。
- 结构：`<maintenance id= name= enable= platform= mode= child1="组名;权重" .../>`
- 自闭合标签，改 `enable="true"→"false"` 即可关闭对应功能位；XML 结构与 `casVersion` 一律不动。
- 同域 `config?name=level|prop|payment|product` 返回 `<error>config X is not exportable</error>`，
  关卡/道具/支付表不对外导出，客户端另有取法，网络层拿不到。

可关闭的广告/推广位（实测 42 条命中，节选）：
`IosVideoAdsFeature`、`VideoSdkEntryV41~V49`、`VideoAdGroup2022`、`ad_control`、
`ad_loading_test`/`_app`/`_h5`、`SplashAd1/4`、`GamePauseAD`、`activity_ad`、
`Promotion_Banner_v1`、`Starwin_Banner`、`level_promotion_difficulty*`。

## 4. 热更新会吃掉所有包内补丁（关键坑）

改了 `Assets/src` 却"完全没效果"时，先查这条链，不要怀疑补丁写错：

| 位置 | 行为 |
|---|---|
| `amf/feature/login/stage/hotfix/HotfixProcessor.lua` | 登录阶段 `DynamicDownloader:execute()`，按 md5 比对从服务端拉缺失/过期 Lua 写入缓存目录 |
| `zoo/wc/static_config_utils.lua:current_md5()` | 优先读 `缓存目录/static_config.md5`，读不到才回落 `ResourceLoader.getCurVersion()` |
| `zoo/wc/static_config_utils.lua:static_config(md5)` | 先读缓存目录，再读包内 `Assets` |
| `zoo/wc/util/skip_dynamic_update.lua` | 有 `skip_dynamic_update.txt` 机制，但 `should_skip` 写死 false |

**绕法（本目录 patch_lua.py 已内置）**：

1. `HotfixProcessor:isHotFixEnabled()` → `return false`，整段跳过下载；
2. `static_config_utils:current_md5()` → 直接 `return ResourceLoader.getCurVersion()`，忽略缓存清单。

改完这两处后，清单指向我们加密后的新文件名，缓存里没有该文件名 → 回落包内 → 读到补丁版。
**不需要删 App 重装**，覆盖安装即可。

## 5. 补丁点（1.163.235 实测）

| 文件 | 改动 | 效果 |
|---|---|---|
| `ubf/.../processFlow/module/UBFProcessEnergyManager.lua` | `getEnergyState()` 直接 `return UserEnergyState.INFINITE` | 进关走无限精力分支 |
| `ubf/.../processFlow/flowNode/UBFSLSendStartLevelProcess.lua` | `costEnergy=false`、`itemList/videoPropList/usePropList={}`、`energyBuff=false` | 进关不申报消耗 |
| `amf/.../assetsbar/energy/AMFUserEnergyManager.lua` | `getInfiniteEnergyEndTime()` → `4102416000000`（2100 年） | UI 体力恒为无限 |
| `amf/middleware/prop/userprop/AMFUserPropsManager.lua` | `getUserPropNumber()` / `getUserTimePropNumber()` → `999` | 道具数量显示 999 |
| `amf/feature/login/stage/hotfix/HotfixProcessor.lua` | `isHotFixEnabled()` → false | 阻止热更新覆盖 |
| `zoo/wc/static_config_utils.lua` | `current_md5()` → `ResourceLoader.getCurVersion()` | 强制用包内清单 |

### 原版自身的一个 bug

```lua
function UBFPropStack:init( initData )
	self.propsType = initData.propsType
	...
	if self.propsType == UsePropsType.INFINITE then self.count = -1 end
	self.count = initData.count        -- ← 无条件覆盖，无限标记当场失效
end
```

`getCount()` 返回 -1 表示无限的约定，被下一行自己覆盖掉了。

## 6. 踩过的坑

**改 `UBFPropUnit:addPropStack` 会导致进关闪退。**
原版有 `if count <= 0 then return end`，把数量为 0 的栈过滤掉。为让"0 个道具也能点"而删掉这行、
无条件 `setCount(999)`，会让所有占位栈（itemId 无效）进入道具栏，构建 UI 时直接崩。
正确做法是只在点击入口 `UBFPropBarModule:_getUsePropContext()` 里就地补数：

```lua
local useStack = unit:getFirstUseStack()
if useStack and useStack:getCount() == 0 then useStack:setCount(999) end
if not useStack then return nil, tostring(propUnitType) .. "道具数量不足" end
```

构建阶段完全不碰，只在使用阶段兜底。

## 7. 真机验证状态

| 版本 | 结果 |
|---|---|
| v1 只改申报字段 | 无可见变化（预期） |
| v2 加显示层 getter | 无变化 → 暴露热更新覆盖问题 |
| v3 绕过热更新 | **道具数量与体力显示生效**（截图确认 999 / ∞） |
| v4 改 addPropStack | 点开始游戏闪退（已回滚） |
| v5 回滚 + 点击兜底 | 未验证 |

结论边界：
- 显示层（getter + 缓存清单）**已确认可改**。
- **数值仍以服务端账本为准**。`getUserPropNumber` 返回 999 只影响 UI；局内真正消费道具时若走服务端校验，
  服务端按真实库存拒绝，Lua 层到这就是天花板，再往上只能 dylib hook 内存值。
- 风车币 / 金条 / 星星一律不可改。

## 8. 复现

```bash
# 1. 下载并脱壳（凭据需与账号 SINF key class 匹配，本例 key class 0x13）
ipatool download -b com.happyelements.1OSAnimal --purchase --non-interactive \
  --keychain-passphrase "$PASS" -o enc.ipa
python3 ~/tools/fairplay-decrypt-v2/decrypt.py enc.ipa dec.ipa --credential credential-0x13.bin

# 2. 打补丁（脚本会自己找 AES key、改 Lua、重新加密、更新清单）
python3 patch_lua.py dec.ipa out_unsigned.ipa

# 3. 自签安装
```
