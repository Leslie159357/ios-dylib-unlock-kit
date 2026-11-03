#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yamby 授权门禁补丁 v3 —— 从环境变量取目标（版本无关）
  VER_INVOKE    : 授权校验调用的 smali 前缀, 如 "Lyb/ۥۖۘۘۖ۫;->ۥۜۜۘۙۗۤ("
  BLANK_INVOKE  : 空串判断调用正则（默认匹配任意 CharSequence 判空）
做法: 只保留"通往校验调用"的那一侧, 把门禁的判空/判长分支拆掉。
"""
import glob, os, re

VER_INVOKE = os.environ["VER_INVOKE"]
BLANK_RE = os.environ.get(
    "BLANK_RE",
    r"invoke-static \{([vp]\d+)\},\s*L[a-z0-9]+/\S+;->\S+\(Ljava/lang/CharSequence;\)Z")
BLANK_INVOKE = re.compile(BLANK_RE)
LEN_INVOKE = re.compile(r"invoke-virtual \{([vp]\d+)\},\s*Ljava/lang/String;->length\(\)I")
MOVERESULT = re.compile(r"^\s*move-result\s+([vp]\d+)\s*$")
BRANCH = re.compile(r"^\s*(if-\w+)\s+([vp]\d+)(?:,\s*([vp]\d+))?,\s*(:\w+)\s*$")


def label_index(lines, name):
    for i, l in enumerate(lines):
        if l.strip() == name:
            return i
    return None


def next_verifier(lines, start, limit=250):
    for i in range(start, min(len(lines), start + limit)):
        if VER_INVOKE in lines[i]:
            return i
    return None


def patch_file(path, log):
    lines = open(path, encoding='utf-8', errors='replace').read().splitlines()
    n_b = n_l = 0

    def do(invoke_re, is_blank):
        nonlocal n_b, n_l
        for i, l in enumerate(lines):
            if not invoke_re.search(l):
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
                if not (bm and bm.group(2) == reg):
                    continue
                tgt = bm.group(4)
                li = label_index(lines, tgt)
                jump_has = li is not None and next_verifier(lines, li) is not None
                fall_has = next_verifier(lines, j) is not None
                if jump_has:
                    lines[j] = f"    goto {tgt}"
                elif fall_has:
                    lines[j] = "    nop  # gate-bypass"
                else:
                    continue
                if is_blank:
                    n_b += 1
                else:
                    n_l += 1
                break

    do(BLANK_INVOKE, True)
    do(LEN_INVOKE, False)
    if n_b or n_l:
        open(path, 'w', encoding='utf-8').write("\n".join(lines) + "\n")
    log.append((path.split('smali/', 1)[-1], n_b, n_l))


log = []
for sm in glob.glob("base_smali/smali*/**/*.smali", recursive=True):
    try:
        t = open(sm, encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    if VER_INVOKE in t:
        patch_file(sm, log)

print(f"{'文件':<44}{'空串门':>8}{'长度门':>8}")
tb = tl = 0
for f, b, l in sorted(log):
    print(f"{f:<44}{b:>8}{l:>8}")
    tb += b; tl += l
print(f"{'合计':<44}{tb:>8}{tl:>8}")
