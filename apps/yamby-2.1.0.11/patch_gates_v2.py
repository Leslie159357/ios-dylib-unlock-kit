#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yamby 授权门禁补丁 v2 —— 改跳转方向（与分支极性无关, 比改寄存器常量可靠）
------------------------------------------------------------------
站点形态（明文 dex）:
    invoke-static {..}, Lhh/<已混淆>;-><blankCheck>(Ljava/lang/CharSequence;)Z
    move-result r1
    if-XX r1, :L1                 <-- ① 空串判断
    invoke-virtual {..}, Ljava/lang/String;->length()I
    move-result r2
    const/16 r3, 0x5
    if-YY r2, r3, :L2             <-- ② 长度判断
    ... <构造 HMAC 生成器> ...
    invoke-static {..}, Lub/<已混淆>;-><verify>(..)Z

做法: 对 ①② 两条分支, 判断"跳转目标侧"还是"落空侧"通往 verify 调用;
      通往 verify 的那一侧设为必定到达 —— 跳转侧则把 if-XX 改成 goto, 落空侧则删掉该 if。
      校验函数本体已在别处patch为 return true, 因此后续必然放行。
"""
import glob, re, os

VER_INVOKE = "Lub/\u06e5\u06da\u06e5\u06d8\u06e7\u06e0\u06e8;->\u06e5\u06dc\u06db\u06eb\u06e6\u06e6("
BLANK_INVOKE = re.compile(r"invoke-static \{([vp]\d+)\},\s*Lhh/\S+;->\S+\(Ljava/lang/CharSequence;\)Z")
LEN_INVOKE = re.compile(r"invoke-virtual \{([vp]\d+)\},\s*Ljava/lang/String;->length\(\)I")
MOVERESULT = re.compile(r"^\s*move-result\s+([vp]\d+)\s*$")
BRANCH = re.compile(r"^\s*(if-\w+)\s+([vp]\d+)(?:,\s*([vp]\d+))?,\s*(:\w+)\s*$")
LABEL = re.compile(r"^\s*(:\w+)\s*$")

def strip_lines(lines):
    """返回 {原始行号: 指令文本}, 跳过 .line/空行/注释"""
    out = {}
    for i, l in enumerate(lines):
        s = l.strip()
        if not s or s.startswith(".line") or s.startswith("#"):
            continue
        out[i] = s
    return out

def label_index(lines, name):
    for i, l in enumerate(lines):
        if l.strip() == name:
            return i
    return None

def next_verifier_after(lines, start, limit=250):
    for i in range(start, min(len(lines), start + limit)):
        if VER_INVOKE in lines[i]:
            return i
    return None

def patch_file(path, log):
    lines = open(path, encoding='utf-8', errors='replace').read().splitlines()
    n_blank = n_len = 0

    # ---- ① 空串检查分支 ----
    for i, l in enumerate(lines):
        m = BLANK_INVOKE.search(l)
        if not m:
            continue
        # move-result 寄存器
        reg = None
        for j in range(i + 1, min(len(lines), i + 12)):
            s = lines[j].strip()
            if not s or s.startswith(".line"):
                continue
            mm = MOVERESULT.match(s)
            if mm:
                reg = mm.group(1)
            break
        if reg is None:
            continue
        # 使用该寄存器的那条分支
        for j in range(i + 1, min(len(lines), i + 20)):
            bm = BRANCH.match(lines[j])
            if bm and bm.group(2) == reg:
                tgt = bm.group(4)
                li = label_index(lines, tgt)
                jump_has = li is not None and next_verifier_after(lines, li) is not None
                fall_has = next_verifier_after(lines, j) is not None
                if jump_has:
                    lines[j] = f"    goto {tgt}"
                elif fall_has:
                    lines[j] = "    nop  # gate-bypass"
                else:
                    continue
                n_blank += 1
                break

    # ---- ② 长度检查分支 ----
    for i, l in enumerate(lines):
        if not LEN_INVOKE.search(l):
            continue
        reg = None
        for j in range(i + 1, min(len(lines), i + 12)):
            s = lines[j].strip()
            if not s or s.startswith(".line"):
                continue
            mm = MOVERESULT.match(s)
            if mm:
                reg = mm.group(1)
            break
        if reg is None:
            continue
        for j in range(i + 1, min(len(lines), i + 20)):
            bm = BRANCH.match(lines[j])
            if bm and bm.group(2) == reg:
                tgt = bm.group(4)
                li = label_index(lines, tgt)
                jump_has = li is not None and next_verifier_after(lines, li) is not None
                fall_has = next_verifier_after(lines, j) is not None
                if jump_has:
                    lines[j] = f"    goto {tgt}"
                elif fall_has:
                    lines[j] = "    nop  # gate-bypass"
                else:
                    continue
                n_len += 1
                break

    if n_blank or n_len:
        open(path, 'w', encoding='utf-8').write("\n".join(lines) + "\n")
    log.append((path.split('smali/')[-1], n_blank, n_len))

log = []
for sm in glob.glob("base_smali/smali*/**/*.smali", recursive=True):
    t = open(sm, encoding='utf-8', errors='replace').read()
    if VER_INVOKE in t:
        patch_file(sm, log)

print(f"{'文件':<46}{'空串门':>8}{'长度门':>8}")
tb = tl = 0
for f, b, l in sorted(log):
    print(f"{f:<46}{b:>8}{l:>8}")
    tb += b; tl += l
print(f"{'合计':<46}{tb:>8}{tl:>8}")
