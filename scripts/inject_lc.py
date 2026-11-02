#!/usr/bin/env python3
"""给 Mach-O 追加 LC_LOAD_DYLIB（利用 load commands 后到首个 section 之间的空洞）"""
import struct, sys

def align8(n):
    return (n + 7) & ~7

def inject(path, dylib_path, out):
    d = bytearray(open(path, 'rb').read())
    magic, = struct.unpack_from('<I', d, 0)
    assert magic == 0xfeedfacf, "not 64-bit mach-o"
    ncmds, sizeofcmds = struct.unpack_from('<II', d, 16)

    # 找到 __TEXT 首个 section 的 fileoff 作为可用边界
    off = 32
    limit = None
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', d, off)
        if cmd == 0x19:  # LC_SEGMENT_64
            nsects, = struct.unpack_from('<I', d, off + 64)
            if nsects and limit is None:
                vmaddr, vmsize, fileoff = struct.unpack_from('<QQQ', d, off + 24)
                if fileoff > 0:
                    limit = fileoff
                else:
                    first = struct.unpack_from('<Q', d, off + 72 + 32)[0]
                    limit = first
        off += size

    end = 32 + sizeofcmds
    name = dylib_path.encode() + b'\0'
    cmd_size = align8(24 + len(name))
    if limit is None or end + cmd_size > limit:
        raise SystemExit(f"no room: end={end:#x} limit={limit}")

    newcmd = struct.pack('<III', 0xc, cmd_size, 24)   # lc_str offset = 24
    newcmd += b'\0' * 12                              # pad header -> string starts at +24
    newcmd += name
    newcmd += b'\0' * (cmd_size - len(newcmd))
    d[end:end + cmd_size] = newcmd
    struct.pack_into('<II', d, 16, ncmds + 1, sizeofcmds + cmd_size)
    open(out, 'wb').write(d)
    print(f"injected {dylib_path} cmdsize={cmd_size} at {end:#x}; ncmds {ncmds}->{ncmds+1}, sizeofcmds {sizeofcmds}->{sizeofcmds+cmd_size}")

if __name__ == '__main__':
    inject(sys.argv[1], sys.argv[2], sys.argv[3])
