// EzLang std/stream 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

typedef struct {
    int64_t handle;
    int32_t kind;
} Stream;

typedef struct { bool ok; Stream value; } OptStream;
typedef struct { bool ok; Blob value; } OptBlob;

typedef struct MemoryStream {
    uint8_t *data;
    int64_t length;
    int64_t capacity;
    int64_t cursor;
    bool closed;
} MemoryStream;

static Blob empty_blob(void) {
    Blob out = {NULL, 0};
    return out;
}

static OptBlob none_blob(void) {
    OptBlob out = {false, {NULL, 0}};
    return out;
}

static OptStream none_stream(void) {
    OptStream out = {false, {0, 0}};
    return out;
}

static MemoryStream *as_memory(Stream stream) {
    if (stream.kind != 1 || stream.handle == 0) return NULL;
    return (MemoryStream *)(intptr_t)stream.handle;
}

static bool ensure_capacity(MemoryStream *stream, int64_t required) {
    if (!stream || required < 0) return false;
    if (required <= stream->capacity) return true;
    int64_t next = stream->capacity > 0 ? stream->capacity : 64;
    while (next < required) {
        if (next > INT64_MAX / 2) return false;
        next *= 2;
    }
    uint8_t *data = (uint8_t *)realloc(stream->data, (size_t)next);
    if (!data) return false;
    stream->data = data;
    stream->capacity = next;
    return true;
}

OptStream streamFromBlob(const Blob *data) {
    MemoryStream *stream = (MemoryStream *)calloc(1, sizeof(MemoryStream));
    if (!stream) return none_stream();
    int64_t size = data && data->data && data->size > 0 ? data->size : 0;
    if (size > 0) {
        stream->data = (uint8_t *)malloc((size_t)size);
        if (!stream->data) {
            free(stream);
            return none_stream();
        }
        memcpy(stream->data, data->data, (size_t)size);
        stream->length = size;
        stream->capacity = size;
    }
    Stream value = {(int64_t)(intptr_t)stream, 1};
    OptStream out = {true, value};
    return out;
}

OptBlob streamRead(const Stream *stream_value, int64_t maxBytes) {
    if (!stream_value || maxBytes < 0) return none_blob();
    MemoryStream *stream = as_memory(*stream_value);
    if (!stream || stream->closed) return none_blob();
    int64_t remaining = stream->length - stream->cursor;
    if (remaining <= 0 || maxBytes == 0) {
        OptBlob out = {true, empty_blob()};
        return out;
    }
    int64_t count = remaining < maxBytes ? remaining : maxBytes;
    uint8_t *data = (uint8_t *)malloc((size_t)count);
    if (!data) return none_blob();
    memcpy(data, stream->data + stream->cursor, (size_t)count);
    stream->cursor += count;
    OptBlob out = {true, {data, count}};
    return out;
}

int64_t streamWrite(const Stream *stream_value, const Blob *data) {
    if (!stream_value || !data || data->size <= 0) return 0;
    MemoryStream *stream = as_memory(*stream_value);
    if (!stream || stream->closed || !data->data) return -1;
    if (!ensure_capacity(stream, stream->length + data->size)) return -1;
    memcpy(stream->data + stream->length, data->data, (size_t)data->size);
    stream->length += data->size;
    return data->size;
}

OptBlob streamToBlob(const Stream *stream_value) {
    if (!stream_value) return none_blob();
    MemoryStream *stream = as_memory(*stream_value);
    if (!stream || stream->closed) return none_blob();
    if (stream->length <= 0) {
        OptBlob out = {true, empty_blob()};
        return out;
    }
    uint8_t *data = (uint8_t *)malloc((size_t)stream->length);
    if (!data) return none_blob();
    memcpy(data, stream->data, (size_t)stream->length);
    OptBlob out = {true, {data, stream->length}};
    return out;
}

int64_t streamCopy(const Stream *dst_value, const Stream *src_value, int64_t bufferSize) {
    if (!dst_value || !src_value) return -1;
    if (bufferSize <= 0) bufferSize = 4096;
    MemoryStream *dst = as_memory(*dst_value);
    MemoryStream *src = as_memory(*src_value);
    if (!dst || !src || dst->closed || src->closed) return -1;
    int64_t copied = 0;
    while (src->cursor < src->length) {
        int64_t remaining = src->length - src->cursor;
        int64_t count = remaining < bufferSize ? remaining : bufferSize;
        if (!ensure_capacity(dst, dst->length + count)) return -1;
        memcpy(dst->data + dst->length, src->data + src->cursor, (size_t)count);
        dst->length += count;
        src->cursor += count;
        copied += count;
    }
    return copied;
}

bool streamFlush(const Stream *stream_value) {
    MemoryStream *stream = stream_value ? as_memory(*stream_value) : NULL;
    return stream != NULL && !stream->closed;
}

bool streamClose(const Stream *stream_value) {
    MemoryStream *stream = stream_value ? as_memory(*stream_value) : NULL;
    if (!stream || stream->closed) return false;
    stream->closed = true;
    free(stream->data);
    stream->data = NULL;
    stream->length = 0;
    stream->capacity = 0;
    stream->cursor = 0;
    free(stream);
    return true;
}
