#!/usr/bin/env python3
"""YQC 式弱加载注入工具：给 Mach-O 添加 LC_LOAD_WEAK_DYLIB（0x80000018）
利用 load commands 区与第一个 section 之间的 padding 空间，不动其它数据。
用法: inject_weak.py <binary> <dylib_path> [更多dylib...]
"""
import struct, sys, os

LC_LOAD_WEAK_DYLIB = 0x80000018

def main(binary, dylibs):
    data = bytearray(open(binary, 'rb').read())
    off = 4
    hdr = struct.unpack_from('<IiiIIII', data, off)
    ncmds, sizeofcmds = hdr[3], hdr[4]
    off += 28
    # 找到 load commands 区末尾到第一个 section 的 gap
    first_sec_off = None
    cmd_end = 32 + sizeofcmds
    # 遍历找最小 fileoff（第一个 section 数据）
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from('<II', data, off)
        if cmd == 0x19:  # segment
            nsects = struct.unpack_from('<I', data, off+64)[0]
            s = off + 72
            for _ in range(nsects):
                sec_off = struct.unpack_from('<I', data, s+48)[0]
                if sec_off > 0 and (first_sec_off is None or sec_off < first_sec_off):
                    first_sec_off = sec_off
                s += 80
        off += cmdsize
    gap = first_sec_off - cmd_end
    print(f"ncmds={ncmds} sizeofcmds={sizeofcmds} cmd_end=0x{cmd_end:x} 首个section=0x{first_sec_off:x} gap={gap}字节")
    # 构造新命令
    new_cmds = bytearray()
    for d in dylibs:
        name = d.encode() + b'\x00'
        cmdsize = (24 + len(name) + 7) & ~7
        new_cmds += struct.pack('<IIIIII', LC_LOAD_WEAK_DYLIB, cmdsize, 24, 0, 0, 0)
        new_cmds += name
        new_cmds += b'\x00' * (cmdsize - 24 - len(name))
        print(f"  + 弱依赖: {d} (cmdsize={cmdsize})")
    if len(new_cmds) > gap:
        print(f"[错误] gap 不够: 需要 {len(new_cmds)} 字节, 只有 {gap}")
        sys.exit(1)
    # 写入
    data[cmd_end:cmd_end+len(new_cmds)] = new_cmds
    # 更新 header（ncmds@16, sizeofcmds@20）
    struct.pack_into('<I', data, 16, ncmds + len(dylibs))
    struct.pack_into('<I', data, 20, sizeofcmds + len(new_cmds))
    open(binary, 'wb').write(data)
    print(f"[OK] 已注入 {len(dylibs)} 个弱依赖, ncmds={ncmds+len(dylibs)} sizeofcmds={sizeofcmds+len(new_cmds)}")

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
