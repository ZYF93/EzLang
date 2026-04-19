"""
EzLang WASI Runtime Simulation
Minimal WASI implementation for testing print and memory operations.
"""

import sys

class WASIRuntime:
    def __init__(self):
        self.memory = bytearray(1024 * 1024)  # 1MB initial memory
        self.memory_size = len(self.memory)

    def fd_write(self, fd: int, iovs_ptr: int, iovs_len: int, nwritten_ptr: int) -> int:
        """
        WASI fd_write: write to file descriptor
        For fd=1 (stdout), print the content
        """
        if fd == 1:  # stdout
            # Simplified: assume iovs contain the string
            # In real WASI, iovs is array of {buf, len}
            # For simulation, we'll just print a placeholder
            print("WASI fd_write: printing to stdout")
            return 0  # success
        return 1  # error

    def memory_grow(self, pages: int) -> int:
        """
        WebAssembly memory.grow: grow memory by pages (64KB each)
        """
        page_size = 64 * 1024
        new_size = self.memory_size + pages * page_size
        if new_size > 1024 * 1024 * 1024:  # 1GB limit
            return -1  # out of memory
        self.memory.extend(bytearray(pages * page_size))
        old_pages = self.memory_size // page_size
        self.memory_size = new_size
        return old_pages

# Global runtime instance
wasi_runtime = WASIRuntime()

def print_function(msg: str):
    """Simulated print function"""
    print(msg)

def memory_grow(pages: int) -> int:
    """Simulated memory.grow"""
    return wasi_runtime.memory_grow(pages)