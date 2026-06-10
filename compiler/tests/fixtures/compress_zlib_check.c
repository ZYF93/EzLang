#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../../packages/std/native/compress.c"

static void print_hex(const Blob blob) {
    for (int64_t i = 0; i < blob.size; ++i) {
        printf("%02x", blob.data[i]);
    }
    putchar('\n');
}

static int expect_text(const OptBlob value, const char *expected) {
    size_t len = strlen(expected);
    return value.ok && value.value.size == (int64_t)len && memcmp(value.value.data, expected, len) == 0;
}

int main(void) {
    const uint8_t text[] = "hello hello hello";
    Blob plain = {(uint8_t *)text, 17};

    OptBlob gz = compressGzip(&plain);
    OptBlob z = compressZlib(&plain);
    OptBlob raw = compressDeflate(&plain);
    if (!gz.ok || !z.ok || !raw.ok) return 1;

    OptBlob gz_text = decompressGzip(&gz.value);
    OptBlob z_text = decompressZlib(&z.value);
    OptBlob raw_text = decompressDeflate(&raw.value);
    if (!expect_text(gz_text, "hello hello hello")) return 2;
    if (!expect_text(z_text, "hello hello hello")) return 3;
    if (!expect_text(raw_text, "hello hello hello")) return 4;

    uint8_t gz_sample_bytes[] = {
        0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x02, 0xff, 0xcb, 0x48, 0xcd, 0xc9, 0xc9, 0x57,
        0xc8, 0x40, 0x90, 0x00, 0x80, 0x88, 0xf9, 0xe5,
        0x11, 0x00, 0x00, 0x00,
    };
    uint8_t z_sample_bytes[] = {
        0x78, 0x9c, 0xcb, 0x48, 0xcd, 0xc9, 0xc9, 0x57,
        0xc8, 0x40, 0x90, 0x00, 0x3a, 0x2e, 0x06, 0x7d,
    };
    uint8_t raw_sample_bytes[] = {
        0xcb, 0x48, 0xcd, 0xc9, 0xc9, 0x57, 0xc8, 0x40, 0x90, 0x00,
    };

    Blob gz_sample = {gz_sample_bytes, (int64_t)sizeof(gz_sample_bytes)};
    Blob z_sample = {z_sample_bytes, (int64_t)sizeof(z_sample_bytes)};
    Blob raw_sample = {raw_sample_bytes, (int64_t)sizeof(raw_sample_bytes)};
    if (!expect_text(decompressGzip(&gz_sample), "hello hello hello")) return 5;
    if (!expect_text(decompressZlib(&z_sample), "hello hello hello")) return 6;
    if (!expect_text(decompressDeflate(&raw_sample), "hello hello hello")) return 7;

    Blob invalid = {(uint8_t *)"not gzip", 8};
    Blob invalid_blob = {NULL, 1};
    if (decompressGzip(&invalid).ok || decompressZlib(&invalid).ok || decompressDeflate(&invalid).ok) return 8;
    if (compressGzip(&invalid_blob).ok || compressZlib(&invalid_blob).ok || compressDeflate(&invalid_blob).ok) return 9;

    print_hex(z.value);
    print_hex(raw.value);
    return 0;
}
