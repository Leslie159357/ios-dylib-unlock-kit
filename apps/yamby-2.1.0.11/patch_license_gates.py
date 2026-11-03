#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yamby 授权门禁静态绕过补丁
------------------------------------------------
原理（全部基于明文 dex 事实）:
  每个 Pro 门禁的形态都是:
      v = hh.<class>.<isNotBlank>(license_str)      ; 1 = 有内容
      if (v == 0) goto LOCKED                        ; 空串 -> 锁
      v = license_str.length()
      if (v < 5) goto LOCKED                         ; 太短 -> 锁
      if (ub.<verify>(gen(31天),  lic)) goto UNLOCK  ; 校验1
      if (ub.<verify>(gen(120天), lic)) goto UNLOCK  ; 校验2
      goto LOCKED
  把 3 个判定结果直接用常量顶掉即可（只改 move-result -> const/4，不动控制流）:
      isNotBlank 结果 -> 1
      length 结果     -> 5 (const/4 只能装 nibble，取边界值 5)
      verify 结果     -> 1
"""
import glob, re, os, sys

VER_INVOKE   = "Lub/\u06e5\u06da\u06e5\u06d8\u06e7\u06e0\u06e8;->\u06e5\u06dc\u06db\u06eb\u06e6\u06e6("
ISNOTBLANK   = re.compile(r"invoke-static \{[vp]\d+\},\s*Lhh/\S+;->\S+\(Ljava/lang/CharSequence;\)Z")
LEN_INVOKE   = re.compile(r"invoke-virtual \{[vp]\d+\},\s*Ljava/lang/String;->length\(\)I")
MOVERESULT   = re.compile(r"^(\s*)move-result(-object)?\s+([vp]\d+)\s*$")

def next_move(lines, i, limit=12):
    """i 之后第一条 move-result 的行号"""
    for j in range(i + 1, min(len(lines), i + limit)):
        s = lines[j].strip()
        if s.startswith(".line") or s.startswith("#") or s == "":
            continue
        if s.startswith("move-result"):
            return j
        return None
    return None

def patch_file(path, log):
    lines = open(path, encoding='utf-8', errors='replace').read().splitlines()
    n_ver = n_blank = n_len = 0
    line_idx = [i for i, l in enumerate(lines) if VER_INVOKE in l]

    # 1) 授权校验结果 -> 1
    for i in line_idx:
        j = next_move(lines, i)
        if j is None: continue
        m = MOVERESULT.match(lines[j])
        if not m: continue
        reg = m.group(3)
        lines[j] = f"{m.group(1)}const/16 {reg}, 0x1"
        n_ver += 1

    # 2) isNotBlank 结果 -> 1
    bl_idx = [i for i, l in enumerate(lines) if ISNOTBLANK.search(l)]
    for i in bl_idx:
        j = next_move(lines, i)
        if j is None: continue
        m = MOVERESULT.match(lines[j])
        if not m: continue
        lines[j] = f"{m.group(1)}const/16 {m.group(3)}, 0x1"
        n_blank += 1

    # 3) 授权序言内的 String.length() -> 100
    #    精确作用域: 每个 isNotBlank 调用之后 40 行内的 length() 调用
    for b in bl_idx:
        for k in range(b, min(len(lines), b + 40)):
            if not LEN_INVOKE.search(lines[k]):
                continue
            j = next_move(lines, k)
            if j is None: continue
            m = MOVERESULT.match(lines[j])
            if not m: continue
            lines[j] = f"{m.group(1)}const/16 {m.group(3)}, 0x5"
            n_len += 1

    open(path, 'w', encoding='utf-8').write("\n".join(lines) + "\n")
    log.append((path.split('smali/')[-1], n_ver, n_blank, n_len))

log = []
for sm in glob.glob("base_smali/smali*/**/*.smali", recursive=True):
    t = open(sm, encoding='utf-8', errors='replace').read()
    if VER_INVOKE in t:
        patch_file(sm, log)

print(f"{'文件':<44}{'verify':>7}{'isNotBlank':>12}{'length':>8}")
tv = tb = tl = 0
for f, a, b, c in sorted(log):
    print(f"{f:<44}{a:>7}{b:>12}{c:>8}")
    tv += a; tb += b; tl += c
print(f"{'合计':<44}{tv:>7}{tb:>12}{tl:>8}")
