// EzLang std/compress 原生封装层
// native 目标使用系统 zlib；未提供 zlib 的工具链会在链接阶段暴露缺失依赖。

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if defined(__APPLE__)
#include <TargetConditionals.h>
#endif

#if defined(__linux__) || defined(__ANDROID__) || defined(__APPLE__) || defined(_WIN32)
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

typedef struct {
    int64_t handle;
    int32_t kind;
} Stream;

typedef struct { bool ok; Blob value; } OptBlob;

OptBlob streamRead(const Stream *stream, int64_t maxBytes);
int64_t streamWrite(const Stream *stream, const Blob *data);
bool streamFlush(const Stream *stream);

static OptBlob ez_none_blob(void) {
    return (OptBlob){false, {NULL, 0}};
}

#if EZ_COMPRESS_HAS_ZLIB
static bool ez_blob_bytes(const Blob *data, const uint8_t **bytes, size_t *size) {
    *bytes = NULL;
    if (!data || data->size < 0 || (data->size > 0 && !data->data)) {
        *size = 0;
        return false;
    }
    if ((uint64_t)data->size > (uint64_t)SIZE_MAX) {
        *size = 0;
        return false;
    }
    *size = (size_t)data->size;
    *bytes = data->data ? data->data : (const uint8_t *)"";
    return true;
}

static OptBlob ez_blob_some(uint8_t *data, size_t size) {
    if (!data && size > 0) return ez_none_blob();
    return (OptBlob){true, {data, (int64_t)size}};
}

static OptBlob ez_deflate_run(const Blob *input, int window_bits) {
    size_t input_size = 0;
    const uint8_t *input_data = NULL;
    if (!ez_blob_bytes(input, &input_data, &input_size)) return ez_none_blob();
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
    const uint8_t *input_data = NULL;
    if (!ez_blob_bytes(input, &input_data, &input_size)) return ez_none_blob();
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

static int64_t ez_stream_chunk_size(int64_t buffer_size) {
    if (buffer_size <= 0) buffer_size = 8192;
    if (buffer_size > 1024 * 1024) buffer_size = 1024 * 1024;
    return buffer_size;
}

static bool ez_add_written(int64_t *total, int64_t written) {
    if (!total || written < 0 || *total > INT64_MAX - written) return false;
    *total += written;
    return true;
}

static int64_t ez_stream_write_all(const Stream *dst, const uint8_t *data, size_t size) {
    if (size == 0) return 0;
    if (!dst || !data || size > (size_t)INT64_MAX) return -1;
    Blob chunk = {(uint8_t *)data, (int64_t)size};
    int64_t written = streamWrite(dst, &chunk);
    return written == (int64_t)size ? written : -1;
}

static int64_t ez_zlib_stream_run(const Stream *dst, const Stream *src, int64_t buffer_size, int window_bits, bool encode) {
    if (!dst || !src) return -1;
    buffer_size = ez_stream_chunk_size(buffer_size);

    z_stream stream;
    memset(&stream, 0, sizeof(stream));
    int init = encode
        ? deflateInit2(&stream, Z_DEFAULT_COMPRESSION, Z_DEFLATED, window_bits, 8, Z_DEFAULT_STRATEGY)
        : inflateInit2(&stream, window_bits);
    if (init != Z_OK) return -1;

    int64_t total = 0;
    bool done = false;
    int status = Z_OK;
    uint8_t out[8192];

    while (!done) {
        OptBlob input = streamRead(src, buffer_size);
        if (!input.ok) {
            if (encode) deflateEnd(&stream);
            else inflateEnd(&stream);
            return -1;
        }

        const uint8_t *input_data = NULL;
        size_t input_size = 0;
        if (!ez_blob_bytes(&input.value, &input_data, &input_size) || input_size > UINT32_MAX) {
            free(input.value.data);
            if (encode) deflateEnd(&stream);
            else inflateEnd(&stream);
            return -1;
        }

        bool eof = input_size == 0;
        stream.next_in = (Bytef *)input_data;
        stream.avail_in = (uInt)input_size;

        do {
            stream.next_out = out;
            stream.avail_out = (uInt)sizeof(out);
            status = encode ? deflate(&stream, eof ? Z_FINISH : Z_NO_FLUSH) : inflate(&stream, Z_NO_FLUSH);

            size_t produced = sizeof(out) - stream.avail_out;
            if (produced > 0) {
                int64_t written = ez_stream_write_all(dst, out, produced);
                if (!ez_add_written(&total, written)) {
                    free(input.value.data);
                    if (encode) deflateEnd(&stream);
                    else inflateEnd(&stream);
                    return -1;
                }
            }

            if (status == Z_STREAM_END) {
                done = true;
                break;
            }
            if (status != Z_OK) {
                free(input.value.data);
                if (encode) deflateEnd(&stream);
                else inflateEnd(&stream);
                return -1;
            }
        } while (stream.avail_in > 0 || stream.avail_out == 0 || (encode && eof));

        free(input.value.data);
        if (eof && !done) {
            if (encode) deflateEnd(&stream);
            else inflateEnd(&stream);
            return -1;
        }
    }

    if (encode) deflateEnd(&stream);
    else inflateEnd(&stream);
    return streamFlush(dst) ? total : -1;
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

int64_t compressGzipStream(const Stream *dst, const Stream *src, int64_t bufferSize) {
#if EZ_COMPRESS_HAS_ZLIB
    return ez_zlib_stream_run(dst, src, bufferSize, 15 + 16, true);
#else
    (void)dst; (void)src; (void)bufferSize;
    return -1;
#endif
}

int64_t decompressGzipStream(const Stream *dst, const Stream *src, int64_t bufferSize) {
#if EZ_COMPRESS_HAS_ZLIB
    return ez_zlib_stream_run(dst, src, bufferSize, 15 + 16, false);
#else
    (void)dst; (void)src; (void)bufferSize;
    return -1;
#endif
}

int64_t compressZlibStream(const Stream *dst, const Stream *src, int64_t bufferSize) {
#if EZ_COMPRESS_HAS_ZLIB
    return ez_zlib_stream_run(dst, src, bufferSize, 15, true);
#else
    (void)dst; (void)src; (void)bufferSize;
    return -1;
#endif
}

int64_t decompressZlibStream(const Stream *dst, const Stream *src, int64_t bufferSize) {
#if EZ_COMPRESS_HAS_ZLIB
    return ez_zlib_stream_run(dst, src, bufferSize, 15, false);
#else
    (void)dst; (void)src; (void)bufferSize;
    return -1;
#endif
}

int64_t compressDeflateStream(const Stream *dst, const Stream *src, int64_t bufferSize) {
#if EZ_COMPRESS_HAS_ZLIB
    return ez_zlib_stream_run(dst, src, bufferSize, -15, true);
#else
    (void)dst; (void)src; (void)bufferSize;
    return -1;
#endif
}

int64_t decompressDeflateStream(const Stream *dst, const Stream *src, int64_t bufferSize) {
#if EZ_COMPRESS_HAS_ZLIB
    return ez_zlib_stream_run(dst, src, bufferSize, -15, false);
#else
    (void)dst; (void)src; (void)bufferSize;
    return -1;
#endif
}
