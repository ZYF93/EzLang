use std::alloc::{alloc, dealloc, Layout};
use std::ptr;

pub struct Arena {
    buffer: *mut u8,
    size: usize,
    cursor: usize,
}

impl Arena {
    pub fn new(size: usize) -> Self {
        let layout = Layout::from_size_align(size, 8).unwrap();
        let buffer = unsafe { alloc(layout) };
        if buffer.is_null() {
            panic!("Arena allocation failed");
        }
        Self {
            buffer,
            size,
            cursor: 0,
        }
    }

    pub fn alloc(&mut self, size: usize, align: usize) -> *mut u8 {
        let aligned_cursor = (self.cursor + align - 1) & !(align - 1);
        if aligned_cursor + size > self.size {
            panic!("Arena out of memory");
        }
        let ptr = unsafe { self.buffer.add(aligned_cursor) };
        self.cursor = aligned_cursor + size;
        ptr
    }

    pub fn reset(&mut self) {
        self.cursor = 0;
    }
}

impl Drop for Arena {
    fn drop(&mut self) {
        let layout = Layout::from_size_align(self.size, 8).unwrap();
        unsafe { dealloc(self.buffer, layout) };
    }
}