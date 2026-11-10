# Xmind iOS 27.01.05101 会员解锁 — 工程存档

包名 `net.xmind.brownieapp`（内部代号 `Yogurt`），iPhone 16 Pro Max / iOS 18.6.2 实测环境。
2026-11-10。

## 结论

会员态由服务端 **RSA 签名的 `raw_data`** 决定，网络层（Loon/MITM）无解；
唯一可行路径是静态补丁本地判定函数。**AI（Agent/Chatbot/生图）除外**，额度在服务端按账号扣。

## 会员接口（实测抓包）

```
POST https://www.xmind.cn/_res/devices          (头 authtoken)
  → {"raw_data":"<RSA 密文>","license":{"status":"Trial","expireTime":0},"_code":200}

GET  https://www.xmind.cn/_res/user_sub_details
  → {"_code":200,"google":[],"appstore":[],"official_website":[]}   // 购买记录列表，非判定源
```

`raw_data` 由客户端 `sub_10042ABE8` 用内置公钥（`XmindConfiguration` 内
`-----BEGIN PUBLIC KEY----- MIGfMA0GCSqGSIb3DQEB...`）调 `SecKeyCreateDecryptedData` 解出明文，
BL 位于 `0x42AD78`。**不要 NOP 这一处**：跳过验签后客户端会去解析被改写过的明文，
字段缺项必崩（v9 那版闪退即此）。

## 六处补丁（全部为函数头 8 字节 → mov/ret）

| 偏移 | 原字节 | 补丁 | 判定入口 | 调用点数 | 覆盖 |
|---|---|---|---|---|---|
| `0x42E2A4` | `ffc306d1 f65718a9` | `60008052 c0035fd6`（mov w0,#3; ret） | PersonalLicenseType | 16 | 档位枚举，0=None 1=Pro 2=Pro Plus 3=Premium |
| `0x4281F0` | `ff8306d1 fc6f16a9` | `60008052 c0035fd6`（mov w0,#3; ret） | 个人会员总闸 | 149 | 导出/主题/模板/附件/Pitch 等；返回非 1 的非零值使 `sub_100CF6A98` 的建图上限变 INT64_MAX |
| `0x42E81C` | `ff8301d1 fa6701a9` | `20008052 c0035fd6`（mov w0,#1; ret） | 团队/公共空间授权 | 44 | 「当前计划最多 3 个思维导图」弹窗的来源 |
| `0x42A5B0` | `f44fbea9 fd7b01a9` | `20008052 c0035fd6` | isPremium | 32 | Premium 档专属功能 |
| `0x42A5FC` | `fc6fbaa9 fa6701a9` | `20008052 c0035fd6` | isProPlus | 40 | Pro Plus 档专属功能 |
| `0x425864` | `fc6fbaa9 fa6701a9` | `20008052 c0035fd6` | 设备 license / Pro | 31 | 离线宽限、设备绑定校验 |

合计 312 个调用点，全部恒真。

## 数量上限的判定链（`sub_100CF6A98`）

```
v17 = sub_1004281F0()      // 个人
  v17==0  -> 弹窗「最多 10 个」
  v17==1  -> 弹窗「最多 50 个」
  其他非零 -> INT64_MAX，直接放行
团队分支
  v23 = sub_10042E81C()    // 团队授权
  v23==0  -> 弹窗「最多 3 个」（公共空间走这条）
```

## 重建步骤

```bash
# 1. 解密（ipatool + fairplay-decrypt-v2，见仓库根 README）
python3 patch.py Payload/Yogurt.app/Yogurt Yogurt.patched
ldid -S entitlements.plist Yogurt.patched          # 自签，用户侧再由 LcSign 重签
# 2. 重新打包：只替换 Payload/Yogurt.app/Yogurt，保留其余 6682 个成员
# 3. 可选：Info.plist CFBundleDisplayName 改成 "Xmind Pro6" 作为版本指纹
```

## 状态

- 静态补丁集与打包流程：已验证（包内字节复核、ldid 签名通过、网关直链 206）
- 真机：v5（三处）用户确认安装成功、公共空间仍弹「3 个」→ 据此补出 `0x42E81C`；
  **v6（六处）尚未拿到用户全功能确认**，属待验收状态

## 配套

- Loon 插件目录：`loon-plugin/plugins/XMind/`（v10 仅展示层归一，不参与解锁）
- 历史无效实现 v2–v9 仍在同目录，仅供考古
