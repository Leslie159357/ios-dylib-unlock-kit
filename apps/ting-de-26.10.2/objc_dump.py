#!/usr/bin/env python3
"""快速解析 iOS Mach-O 的 ObjC 类/方法元数据（chained fixups 版）"""
import struct, sys

IMAGE_BASE = 0x100000000

class MachO:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        magic, cputype, cpusub, ft, ncmds, sizeofcmds = struct.unpack('<IiIIII', self.d[:24])
        assert magic == 0xfeedfacf, hex(magic)
        self.segs = {}
        self.sections = {}
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

    def foff(self, vmaddr):
        """vmaddr -> file offset（本二进制 __TEXT vmaddr=0x100000000, fileoff=0）"""
        return vmaddr - IMAGE_BASE

    def u64(self, fileoff):
        return struct.unpack('<Q', self.d[fileoff:fileoff+8])[0]

    def u32(self, fileoff):
        return struct.unpack('<I', self.d[fileoff:fileoff+4])[0]

    def decode_ptr(self, fileoff):
        """解码指针 -> 目标 file offset；bind 返回 None"""
        raw = self.u64(fileoff)
        if raw == 0:
            return None
        # 普通 vmaddr（未做 chained fixup 的 ro 数据）
        if IMAGE_BASE <= raw < IMAGE_BASE + 0x4000000:   # 仅 __TEXT 范围(64MB)视为明文 vmaddr
            return raw - IMAGE_BASE
        is_bind = (raw >> 63) & 1
        if is_bind:
            return None
        target = raw & 0xFFFFFFFFF
        return target

    def cstr(self, fileoff):
        end = self.d.find(b'\0', fileoff)
        return self.d[fileoff:end].decode('utf-8', 'ignore')


def method_list(m, vmaddr):
    """返回 [(sel, types, imp_vmaddr)]"""
    fo = m.foff(vmaddr) if vmaddr >= IMAGE_BASE else vmaddr
    entsize_flags = m.u32(fo)
    count = m.u32(fo + 4)
    entsize = entsize_flags & 0xFFFC
    out = []
    for i in range(count):
        e = fo + 8 + i * entsize
        selref_fo = m.decode_ptr(e)
        typesref_fo = m.decode_ptr(e + 8)
        imp_raw = m.u64(e + 16)
        sel = "?"
        if selref_fo is not None:
            try:
                str_fo = m.decode_ptr(selref_fo)
                sel = m.cstr(str_fo if str_fo is not None else selref_fo)
            except Exception:
                sel = "?"
        types_fo = None
        if typesref_fo is not None:
            try:
                types_fo = m.decode_ptr(typesref_fo)
            except Exception:
                types_fo = None
        tp = ""
        if types_fo is not None and 0 < types_fo < len(m.d):
            try:
                tp = m.cstr(types_fo)
            except Exception:
                pass
        out.append((sel, tp, imp_raw))
    return out


def property_list(m, vmaddr):
    fo = m.foff(vmaddr) if vmaddr >= IMAGE_BASE else vmaddr
    entsize = m.u32(fo) & 0xFFFC
    count = m.u32(fo + 4)
    out = []
    for i in range(count):
        e = fo + 8 + i * entsize
        name_fo = m.decode_ptr(e)
        attr_fo = m.decode_ptr(e + 8)
        try:
            nm = m.cstr(name_fo) if name_fo else "?"
        except Exception:
            nm = "?"
        try:
            at = m.cstr(attr_fo) if attr_fo else ""
        except Exception:
            at = ""
        out.append((nm, at))
    return out


def ivar_list(m, vmaddr):
    fo = m.foff(vmaddr) if vmaddr >= IMAGE_BASE else vmaddr
    entsize = m.u32(fo) & 0xFFFC
    count = m.u32(fo + 4)
    out = []
    for i in range(count):
        e = fo + 8 + i * entsize
        offp = m.decode_ptr(e)
        name_fo = m.decode_ptr(e + 8)
        type_fo = m.decode_ptr(e + 16)
        try:
            nm = m.cstr(name_fo) if name_fo else "?"
        except Exception:
            nm = "?"
        try:
            tp = m.cstr(type_fo) if type_fo else ""
        except Exception:
            tp = ""
        try:
            offset = struct.unpack('<I', m.d[offp:offp+4])[0] if offp else 0
        except Exception:
            offset = 0
        out.append((nm, tp, offset))
    return out


def all_classes(m):
    saddr, ssize, soff = m.sections['__objc_classlist']
    n = ssize // 8
    classes = []
    for i in range(n):
        cls_fo = m.decode_ptr(soff + i * 8)
        if cls_fo is None:
            continue
        # class_t.data at +32
        data_ptr = m.decode_ptr(cls_fo + 32)
        if data_ptr is None:
            continue
        ro = data_ptr & ~0x7
        ro_fo = m.foff(ro) if ro >= IMAGE_BASE else ro
        name_fo = m.decode_ptr(ro_fo + 24)
        try:
            name = m.cstr(name_fo) if name_fo else "?"
        except Exception:
            name = "?"
        methods_vm = m.decode_ptr(ro_fo + 32)
        props_vm = m.decode_ptr(ro_fo + 64)
        ivars_vm = m.decode_ptr(ro_fo + 48)
        classes.append({
            'name': name, 'fileoff': cls_fo, 'ro': ro_fo,
            'methods_vm': methods_vm, 'props_vm': props_vm, 'ivars_vm': ivars_vm,
        })
    return classes


if __name__ == '__main__':
    m = MachO(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else 'grep'
    arg = sys.argv[3] if len(sys.argv) > 3 else ''
    classes = all_classes(m)
    print(f"# classes: {len(classes)}", file=sys.stderr)
    if mode == 'grep':
        import re
        pat = re.compile(arg, re.I)
        for c in classes:
            hit_cls = pat.search(c['name'])
            ms = method_list(m, c['methods_vm']) if c['methods_vm'] else []
            ps = property_list(m, c['props_vm']) if c['props_vm'] else []
            hit_m = [x for x in ms if pat.search(x[0])]
            hit_p = [x for x in ps if pat.search(x[0])]
            if hit_cls or hit_m or hit_p:
                print(f"\n=== {c['name']} (ro=0x{c['ro']:x}) ===")
                if hit_p:
                    for nm, at in hit_p:
                        print(f"  prop  {nm}  [{at}]")
                for sel, tp, imp in hit_m:
                    print(f"  -[{c['name']} {sel}]  {tp}")
    elif mode == 'class':
        for c in classes:
            if c['name'] == arg:
                ms = method_list(m, c['methods_vm']) if c['methods_vm'] else []
                ps = property_list(m, c['props_vm']) if c['props_vm'] else []
                iv = ivar_list(m, c['ivars_vm']) if c['ivars_vm'] else []
                print(f"=== {c['name']} ===")
                print("props:")
                for nm, at in ps:
                    print(f"  {nm} [{at}]")
                print("ivars:")
                for nm, tp, o in iv:
                    print(f"  {nm} {tp} @{o}")
                print(f"methods ({len(ms)}):")
                for sel, tp, imp in ms:
                    print(f"  - {sel} {tp} imp=0x{imp:x}")
