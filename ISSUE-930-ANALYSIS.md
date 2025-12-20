# Issue #930: musl builds don't work with pyroute2

## Summary

The musl builds from python-build-standalone fail when using `pyroute2` (a Python library for netlink sockets). Operations like `pyroute2.IPRoute()` hang indefinitely, and when interrupted, produce:

```
OSError: getsockaddrlen: bad family
```

## Root Cause Analysis

The issue is that **AF_NETLINK support is not being compiled into Python's socket module** for musl builds.

### Technical Details

1. **CPython's socketmodule.h** (lines ~180-190) contains:
   ```c
   #ifdef HAVE_LINUX_NETLINK_H
   # ifdef HAVE_ASM_TYPES_H
   #  include <asm/types.h>
   # endif
   # include <linux/netlink.h>
   #elif defined(HAVE_NETLINK_NETLINK_H)
   # include <netlink/netlink.h>
   #else
   #  undef AF_NETLINK
   #endif
   ```

2. **CPython's configure.ac** checks for these headers:
   ```
   AC_CHECK_HEADERS([... asm/types.h ...])
   AC_CHECK_HEADERS([linux/netlink.h netlink/netlink.h], [], [], [
   #ifdef HAVE_ASM_TYPES_H
   #include <asm/types.h>
   #endif
   ])
   ```

3. **The problem with musl builds:**
   - The `musl-clang` wrapper redirects the compiler to use musl headers
   - Linux kernel headers (`<linux/netlink.h>`, `<asm/types.h>`) are NOT included in the musl toolchain
   - Without these headers, the configure checks fail
   - `HAVE_LINUX_NETLINK_H` and `HAVE_ASM_TYPES_H` are not defined in pyconfig.h
   - socketmodule.h then executes `#undef AF_NETLINK`
   - All AF_NETLINK socket support is disabled at compile time

4. **Runtime behavior:**
   - Socket creation with `AF_NETLINK` still works (it's a kernel syscall)
   - But when Python tries to parse the socket address from `recvfrom()`, it doesn't recognize `AF_NETLINK`
   - The `getsockaddrlen()` function returns 0 for unknown families
   - This triggers the "OSError: getsockaddrlen: bad family" error

### Why glibc builds work

For glibc builds:
- The clang toolchain includes Linux kernel headers in the sysroot
- `<asm/types.h>` and `<linux/netlink.h>` are found during configure
- `HAVE_LINUX_NETLINK_H` is defined
- AF_NETLINK support is compiled in

### Why Alpine's Python works

Alpine Linux's Python packages are built with:
- `linux-headers` package installed (provides kernel headers sanitized for musl)
- Headers like `<linux/netlink.h>` are available in `/usr/include`

## Potential Fixes

### Option 1: Add kernel headers to the musl toolchain

Integrate [sabotage-linux/kernel-headers](https://github.com/sabotage-linux/kernel-headers) (Linux kernel headers sanitized for musl) into the musl build:

1. Download kernel-headers during toolchain build
2. Install to `/tools/host/include` alongside musl headers
3. Ensure `musl-clang` can find them

### Option 2: Add kernel headers as a dependency for musl builds

Similar to how other dependencies (ncurses, openssl, etc.) are handled:

1. Create a `build-kernel-headers.sh` script
2. Add `kernel-headers` to the `needs` list for musl targets in `targets.yml`
3. Install headers to `/tools/deps/include`

### Option 3: Patch CPython to bundle netlink structures

Add a fallback that defines `struct sockaddr_nl` inline when the header is missing. However, this is fragile and not recommended.

## Verification Steps

To verify this is the issue, check the pyconfig.h in a musl build:

```bash
# Should return nothing if the issue is present
grep "HAVE_LINUX_NETLINK_H" /path/to/musl/python/include/python3.X/pyconfig.h
grep "HAVE_ASM_TYPES_H" /path/to/musl/python/include/python3.X/pyconfig.h
```

If both are missing, AF_NETLINK support is disabled.

## References

- [pyroute2 documentation](https://docs.pyroute2.org/)
- [CPython socketmodule.h](https://github.com/python/cpython/blob/main/Modules/socketmodule.h)
- [sabotage-linux/kernel-headers](https://github.com/sabotage-linux/kernel-headers)
- [musl FAQ on kernel headers](https://wiki.musl-libc.org/faq)
- [Debian bug #215937](https://bugs.debian.org/215937) - Historical issues with linux/netlink.h
