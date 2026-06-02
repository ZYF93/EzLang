// EzLang std/compress 原生封装层
// Linux/macOS 使用系统 zlib；其它 native 目标当前返回空可选值。

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if defined(__APPLE__)
#include <TargetConditionals.h>
#endif

#if (defined(__linux__) && !defined(__ANDROID__)) || (defined(__APPLE__) && (!defined(TARGET_OS_IPHONE) || !TARGET_OS_IPHONE))
#define EZ_COMPRESS_HAS_ZLIB 1
#else
#define EZ_COMPRESS_HAS_ZLIB 0
#endif

#if EZ_COMPRESS_HAS_ZLIB
#include <zlib.h>
#endif

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

typedef struct { bool ok; Blob value; } OptBlob;

static OptBlob ez_none_blob(void) {
    return (OptBlob){false, {NULL, 0}};
}

#if EZ_COMPRESS_HAS_ZLIB
static const uint8_t *ez_blob_bytes(const Blob *data, size_t *size) {
    if (!data || data->size < 0 || (data->size > 0 && !data->data)) {
        *size = 0;
        return NULL;
    }
    *size = (size_t)data->size;
    return data->data ? data->data : (const uint8_t *)"";
}

static OptBlob ez_blob_some(uint8_t *data, size_t size) {
    if (!data && size > 0) return ez_none_blob();
    return (OptBlob){true, {data, (int64_t)size}};
}

static OptBlob ez_deflate_run(const Blob *input, int window_bits) {
    size_t input_size = 0;
    const uint8_t *input_data = ez_blob_bytes(input, &input_size);
    if (!input_data && input_size > 0) return ez_none_blob();
    if (input_size > UINT32_MAX) return ez_none_blob();

    z_stream stream;
    memset(&stream, 0, sizeof(stream));
    if (deflateInit2(&stream, Z_DEFAULT_COMPRESSION, Z_DEFLATED, window_bits, 8, Z_DEFAULT_STRATEGY) != Z_OK) {
        return ez_none_blob();
    }

    size_t capacity = deflateBound(&stream, (uLong)input_size);
    if (capacity == 0) capacity = 64;
    uint8_t *out = (uint8_t *)malloc(capacity);
    if (!out) {
        deflateEnd(&stream);
        return ez_none_blob();
    }

    stream.next_in = (Bytef *)input_data;
    stream.avail_in = (uInt)input_size;
    stream.next_out = out;
    stream.avail_out = (uInt)capacity;

    int status = deflate(&stream, Z_FINISH);
    if (status != Z_STREAM_END) {
        free(out);
        deflateEnd(&stream);
        return ez_none_blob();
    }

    size_t output_size = stream.total_out;
    deflateEnd(&stream);
    uint8_t *exact = output_size == 0 ? NULL : (uint8_t *)realloc(out, output_size);
    if (output_size == 0) free(out);
    else if (exact) out = exact;
    return ez_blob_some(output_size == 0 ? NULL : out, output_size);
}

static bool ez_grow_output(uint8_t **data, size_t *capacity, size_t used) {
    size_t next = *capacity ? *capacity * 2 : 8192;
    if (next < used + 8192) next = used + 8192;
    if (next < *capacity) return false;
    uint8_t *grown = (uint8_t *)realloc(*data, next);
    if (!grown) return false;
    *data = grown;
    *capacity = next;
    return true;
}

static OptBlob ez_inflate_run(const Blob *input, int window_bits) {
    size_t input_size = 0;
    const uint8_t *input_data = ez_blob_bytes(input, &input_size);
    if (!input_data && input_size > 0) return ez_none_blob();
    if (input_size > UINT32_MAX) return ez_none_blob();

    z_stream stream;
    memset(&stream, 0, sizeof(stream));
    if (inflateInit2(&stream, window_bits) != Z_OK) return ez_none_blob();

    size_t capacity = input_size > 0 ? input_size * 3 : 8192;
    if (capacity < 8192) capacity = 8192;
    uint8_t *out = (uint8_t *)malloc(capacity);
    if (!out) {
        inflateEnd(&stream);
        return ez_none_blob();
    }

    stream.next_in = (Bytef *)input_data;
    stream.avail_in = (uInt)input_size;
    int status = Z_OK;
    while (status != Z_STREAM_END) {
        size_t used = stream.total_out;
        if (used == capacity && !ez_grow_output(&out, &capacity, used)) {
            free(out);
            inflateEnd(&stream);
            return ez_none_blob();
        }
        stream.next_out = out + used;
        stream.avail_out = (uInt)(capacity - used);
        status = inflate(&stream, Z_NO_FLUSH);
        if (status == Z_STREAM_END) break;
        if (status != Z_OK) {
            free(out);
            inflateEnd(&stream);
            return ez_none_blob();
        }
        if (stream.avail_out != 0 && stream.avail_in == 0) {
            free(out);
            inflateEnd(&stream);
            return ez_none_blob();
        }
    }

    size_t output_size = stream.total_out;
    inflateEnd(&stream);
    uint8_t *exact = output_size == 0 ? NULL : (uint8_t *)realloc(out, output_size);
    if (output_size == 0) free(out);
    else if (exact) out = exact;
    return ez_blob_some(output_size == 0 ? NULL : out, output_size);
}
#endif

OptBlob compressGzip(const Blob *data) {
#if EZ_COMPRESS_HAS_ZLIB
    return ez_deflate_run(data, 15 + 16);
#else
    (void)data;
    return ez_none_blob();
#endif
}

OptBlob decompressGzip(const Blob *data) {
#if EZ_COMPRESS_HAS_ZLIB
    return ez_inflate_run(data, 15 + 16);
#else
    (void)data;
    return ez_none_blob();
#endif
}

OptBlob compressZlib(const Blob *data) {
#if EZ_COMPRESS_HAS_ZLIB
    return ez_deflate_run(data, 15);
#else
    (void)data;
    return ez_none_blob();
#endif
}

OptBlob decompressZlib(const Blob *data) {
#if EZ_COMPRESS_HAS_ZLIB
    return ez_inflate_run(data, 15);
#else
    (void)data;
    return ez_none_blob();
#endif
}

OptBlob compressDeflate(const Blob *data) {
#if EZ_COMPRESS_HAS_ZLIB
    return ez_deflate_run(data, -15);
#else
    (void)data;
    return ez_none_blob();
#endif
}

OptBlob decompressDeflate(const Blob *data) {
#if EZ_COMPRESS_HAS_ZLIB
    return ez_inflate_run(data, -15);
#else
    (void)data;
    return ez_none_blob();
#endif
}
