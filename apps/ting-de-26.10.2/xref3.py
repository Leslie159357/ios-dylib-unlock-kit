#!/usr/bin/env python3
"""快速 arm64 xref：原始字节扫 adrp，再配 add/ldr，定位引用指定地址的指令"""
import struct, sys

IMAGE_BASE = 0x100000000

class M:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        magic, cputype, cpusub, ft, ncmds, sizeofcmds = struct.unpack('<IiIIII', self.d[:24])
        assert magic == 0xfeedfacf
        self.sections = {}
        self.segs = {}
        off = 32
        for _ in range(ncmds):
            cmd, sz = struct.unpack('<II', self.d[off:off+8])
            if cmd == 0x19:
                name = self.d[off+8:off+24].split(b'\0')[0].decode()
                vmaddr, vmsize, fileoff, filesize = struct.unpack('<QQQQ', self.d[off+24:off+56])
                self.segs[name] = (vmaddr, vmsize, fileoff, filesize)
                nsects = struct.unpack('<I', self.d[off+64:off+68])[0]
                s = off + 72
                for _j in range(nsects):
                    sn = self.d[s:s+16].split(b'\0')[0].decode()
                    saddr, ssize = struct.unpack('<QQ', self.d[s+32:s+48])
                    soff = struct.unpack('<I', self.d[s+48:s+52])[0]
                    self.sections[sn] = (saddr, ssize, soff)
                    s += 80
            off += sz

    def u64(self, fo):
        return struct.unpack('<Q', self.d[fo:fo+8])[0]

    def decode_ptr(self, fo):
        raw = self.u64(fo)
        if raw == 0:
            return None
        if IMAGE_BASE <= raw < IMAGE_BASE + 0x4000000:
            return raw
        if (raw >> 63) & 1:
            return None
        return IMAGE_BASE + (raw & 0xFFFFFFFFF)

    def find_string(self, s):
        b = s.encode() + b'\0'
        out = []
        start = 0
        while True:
            i = self.d.find(b, start)
            if i < 0:
                break
            for name, (va, vs, fo, fs) in self.segs.items():
                if fo <= i < fo + fs:
                    out.append(va + (i - fo))
                    break
            start = i + 1
        return out

    def selrefs_for(self, vmaddrs):
        res = []
        saddr, ssize, soff = self.sections['__objc_selrefs']
        target = set(vmaddrs)
        for i in range(ssize // 8):
            p = self.decode_ptr(soff + i * 8)
            if p in target:
                res.append(saddr + i * 8)
        return res


def decode_adrp(w, pc):
    immhi = (w >> 5) & 0x7FFFF
    immlo = (w >> 29) & 0x3
    imm = (immhi << 2) | immlo
    if imm & (1 << 20):
        imm -= (1 << 21)
    return ((pc & ~0xFFF) + (imm << 12))


def is_adrp(w):
    return (w & 0x9F000000) == 0x90000000


def decode_add_imm(w):
    # ADD (immediate) 64-bit: sf=1 op=0 S=0 -> 0x91000000 mask
    if (w & 0xFF800000) == 0x91000000:
        rd = w & 0x1F
        rn = (w >> 5) & 0x1F
        imm = (w >> 10) & 0xFFF
        sh = (w >> 22) & 1
        if sh:
            imm <<= 12
        return ('add', rd, rn, imm)
    return None


def decode_ldr_imm(w):
    # LDR (immediate) 64-bit unsigned offset: 0xF9400000
    if (w & 0xFFC00000) == 0xF9400000:
        rt = w & 0x1F
        rn = (w >> 5) & 0x1F
        imm = ((w >> 10) & 0xFFF) * 8
        return ('ldr', rt, rn, imm)
    return None


def scan(m, targets, max_hits=80):
    saddr, ssize, soff = m.sections['__text']
    code = m.d[soff:soff + ssize]
    tset = set(targets)
    hits = []
    n = len(code) - 16
    for i in range(0, n, 4):
        w = struct.unpack_from('<I', code, i)[0]
        if not is_adrp(w):
            continue
        pc = saddr + i
        page = decode_adrp(w, pc)
        rd = w & 0x1F
        # 后续 3 条指令
        for k in range(1, 4):
            w2 = struct.unpack_from('<I', code, i + k * 4)[0]
            d = decode_add_imm(w2) or decode_ldr_imm(w2)
            if not d:
                continue
            kind, rdst, rn, imm = d
            if rn == rd:
                full = page + imm
                if full in tset:
                    hits.append((pc, full, kind))
                    if len(hits) >= max_hits:
                        return hits
    return hits


if __name__ == '__main__':
    m = M(sys.argv[1])
    names = sys.argv[2].split(',')
    for s in names:
        vms = m.find_string(s)
        srs = m.selrefs_for(vms) if vms else []
        targets = list(vms) + list(srs)
        print(f"\n##### {s}")
        print(f"  str={[hex(v) for v in vms]} selref={[hex(v) for v in srs]}")
        hits = scan(m, targets)
        print(f"  命中 {len(hits)}:")
        for pc, full, kind in hits[:30]:
            print(f"    {hex(pc)}  -> {hex(full)} ({kind})")
