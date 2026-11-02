#!/usr/bin/env python3
"""Scripting 3.2.1 — ScriptingKit entitlement bypass (static prologue patch).
Each target is a synchronous Bool-returning gate: replace prologue with `mov w0,#1; ret`.
"""
import sys, hashlib, json
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

SRC, DST = sys.argv[1], sys.argv[2]
PATCH = bytes.fromhex("20008052c0035fd6")  # mov w0,#1 ; ret

TARGETS = [
    # (addr, label)
    (0x1007720, "EntitlementOracle.check(_:now:) thunk"),
    (0x1008f08, "EntitlementOracle.check(now:) body"),
    (0x101b930, "ProAccessGuard.hasPro(now:)"),
    (0x101b97c, "ProAccessGuard.hasValidProToken(now:)"),
    (0xd0eb44, "PurchaseManager.isProEnabled"),
    (0xd0ec44, "PurchaseManager.isProStateResolved"),
    (0xd0ec9c, "PurchaseManager.hasLTAccess"),
    (0xd0f29c, "PurchaseManager.hasSubscription"),
]

data = bytearray(open(SRC, "rb").read())
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
report = []
for addr, label in TARGETS:
    orig = bytes(data[addr:addr+8])
    ins = next(iter(md.disasm(orig, addr, 1)))
    if orig == PATCH:
        report.append(f"SKIP already patched {label} @{addr:#x}")
        continue
    data[addr:addr+8] = PATCH
    report.append(f"PATCH {label} @{addr:#x}: {ins.mnemonic} {ins.op_str}  ({orig.hex()}) -> mov w0,#1; ret")

open(DST, "wb").write(data)
sha_before = hashlib.sha256(open(SRC,'rb').read()).hexdigest()
sha_after = hashlib.sha256(bytes(data)).hexdigest()
print("\n".join(report))
print(f"src sha256 {sha_before}")
print(f"dst sha256 {sha_after}")
json.dump({"src":SRC,"dst":DST,"sha_src":sha_before,"sha_dst":sha_after,
           "patches":[{"addr":hex(a),"label":l} for a,l in TARGETS]},
          open("/opt/data/projects/scripting-re/evidence/patch-report.json","w"), indent=1)
