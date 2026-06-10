// EzLang std/stream 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
typedef SOCKET stream_socket_t;
#define STREAM_INVALID_SOCKET INVALID_SOCKET
#define stream_close_socket closesocket
#else
#include <errno.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int stream_socket_t;
#define STREAM_INVALID_SOCKET (-1)
#define stream_close_socket close
#endif

#define STREAM_KIND_MEMORY 1
#define STREAM_KIND_FILE_READ 2
#define STREAM_KIND_FILE_WRITE 3
#define STREAM_KIND_TCP 4
#define STREAM_KIND_PROCESS_STDIN 5
#define STREAM_KIND_PROCESS_STDOUT 6
#define STREAM_KIND_PROCESS_STDERR 7

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

typedef struct FileStream {
    FILE *file;
    int32_t kind;
    bool closed;
} FileStream;

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

static bool blob_valid(const Blob *data) {
    return data && data->size >= 0 && (data->size == 0 || data->data);
}

static bool fits_size_t_i64(int64_t value) {
    return value >= 0 && (uint64_t)value <= (uint64_t)SIZE_MAX;
}

static bool blob_size_valid(const Blob *data) {
    return blob_valid(data) && fits_size_t_i64(data->size);
}

static bool add_i64_overflows(int64_t left, int64_t right, int64_t *out) {
    if (right > 0 && left > INT64_MAX - right) return true;
    if (right < 0 && left < INT64_MIN - right) return true;
    if (out) *out = left + right;
    return false;
}

static MemoryStream *as_memory(Stream stream) {
    if (stream.kind != STREAM_KIND_MEMORY || stream.handle == 0) return NULL;
    return (MemoryStream *)(intptr_t)stream.handle;
}

static FileStream *as_file(Stream stream, int32_t expected_kind) {
    if (stream.kind != expected_kind || stream.handle == 0) return NULL;
    return (FileStream *)(intptr_t)stream.handle;
}

static stream_socket_t as_tcp_socket(Stream stream) {
    if (stream.kind != STREAM_KIND_TCP || stream.handle == 0) return STREAM_INVALID_SOCKET;
    return (stream_socket_t)stream.handle;
}

static bool is_process_read_kind(int32_t kind) {
    return kind == STREAM_KIND_PROCESS_STDOUT || kind == STREAM_KIND_PROCESS_STDERR;
}

static bool is_process_kind(int32_t kind) {
    return kind == STREAM_KIND_PROCESS_STDIN || is_process_read_kind(kind);
}

static bool as_process_handle(Stream stream) {
    return is_process_kind(stream.kind) && stream.handle != 0;
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
    if (!blob_size_valid(data)) return none_stream();
    MemoryStream *stream = (MemoryStream *)calloc(1, sizeof(MemoryStream));
    if (!stream) return none_stream();
    int64_t size = data->size;
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
    Stream value = {(int64_t)(intptr_t)stream, STREAM_KIND_MEMORY};
    OptStream out = {true, value};
    return out;
}

Stream streamFromTcpHandle(int64_t handle) {
    Stream stream = {handle, STREAM_KIND_TCP};
    return stream;
}

static OptStream open_file_stream(const char *path, const char *mode, int32_t kind) {
    if (!path || path[0] == '\0') return none_stream();
    FILE *file = fopen(path, mode);
    if (!file) return none_stream();
    FileStream *stream = (FileStream *)calloc(1, sizeof(FileStream));
    if (!stream) {
        fclose(file);
        return none_stream();
    }
    stream->file = file;
    stream->kind = kind;
    Stream value = {(int64_t)(intptr_t)stream, kind};
    OptStream out = {true, value};
    return out;
}

OptStream streamOpenFileRead(const char *path) {
    return open_file_stream(path, "rb", STREAM_KIND_FILE_READ);
}

OptStream streamOpenFileWrite(const char *path) {
    return open_file_stream(path, "wb", STREAM_KIND_FILE_WRITE);
}

OptBlob streamRead(const Stream *stream_value, int64_t maxBytes) {
    if (!stream_value || maxBytes < 0) return none_blob();
    MemoryStream *stream = as_memory(*stream_value);
    if (stream) {
        if (stream->closed) return none_blob();
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

    FileStream *file_stream = as_file(*stream_value, STREAM_KIND_FILE_READ);
    if (file_stream) {
        if (file_stream->closed || !file_stream->file) return none_blob();
        if (maxBytes == 0) {
            OptBlob out = {true, empty_blob()};
            return out;
        }
        if (!fits_size_t_i64(maxBytes)) return none_blob();
        uint8_t *data = (uint8_t *)malloc((size_t)maxBytes);
        if (!data) return none_blob();
        size_t count_size = fread(data, 1, (size_t)maxBytes, file_stream->file);
        if (count_size == 0 && ferror(file_stream->file)) {
            free(data);
            return none_blob();
        }
        if (count_size == 0) {
            free(data);
            OptBlob out = {true, empty_blob()};
            return out;
        }
        int64_t count = (int64_t)count_size;
        OptBlob out = {true, {data, count}};
        return out;
    }

    if (is_process_read_kind(stream_value->kind) && as_process_handle(*stream_value)) {
        if (maxBytes == 0) {
            OptBlob out = {true, empty_blob()};
            return out;
        }
        if (maxBytes > 1024 * 1024 * 16) maxBytes = 1024 * 1024 * 16;
        uint8_t *data = (uint8_t *)malloc((size_t)maxBytes);
        if (!data) return none_blob();
#if defined(_WIN32)
        DWORD read_size = 0;
        if (!ReadFile((HANDLE)(intptr_t)stream_value->handle, data, (DWORD)maxBytes, &read_size, NULL)) {
            DWORD err = GetLastError();
            free(data);
            if (err == ERROR_BROKEN_PIPE || err == ERROR_HANDLE_EOF) {
                OptBlob out = {true, empty_blob()};
                return out;
            }
            return none_blob();
        }
        if (read_size == 0) {
            free(data);
            OptBlob out = {true, empty_blob()};
            return out;
        }
        OptBlob out = {true, {data, (int64_t)read_size}};
        return out;
#else
        ssize_t got = 0;
        do {
            got = read((int)stream_value->handle, data, (size_t)maxBytes);
        } while (got < 0 && errno == EINTR);
        if (got < 0) {
            free(data);
            return none_blob();
        }
        if (got == 0) {
            free(data);
            OptBlob out = {true, empty_blob()};
            return out;
        }
        OptBlob out = {true, {data, (int64_t)got}};
        return out;
#endif
    }

    stream_socket_t sock = as_tcp_socket(*stream_value);
    if (sock == STREAM_INVALID_SOCKET) return none_blob();
    if (maxBytes == 0) {
        OptBlob out = {true, empty_blob()};
        return out;
    }
    if (maxBytes > 1024 * 1024 * 16) maxBytes = 1024 * 1024 * 16;
    uint8_t *data = (uint8_t *)malloc((size_t)maxBytes);
    if (!data) return none_blob();
#if defined(_WIN32)
    int got = recv(sock, (char *)data, (int)maxBytes, 0);
#else
    ssize_t got = recv(sock, data, (size_t)maxBytes, 0);
#endif
    if (got < 0) {
        free(data);
        return none_blob();
    }
    if (got == 0) {
        free(data);
        OptBlob out = {true, empty_blob()};
        return out;
    }
    int64_t count = (int64_t)got;
    OptBlob out = {true, {data, count}};
    return out;
}

int64_t streamWrite(const Stream *stream_value, const Blob *data) {
    if (!stream_value || !blob_size_valid(data)) return -1;
    MemoryStream *stream = as_memory(*stream_value);
    if (stream) {
        if (stream->closed) return -1;
        if (data->size == 0) return 0;
        if (!data->data) return -1;
        int64_t required = 0;
        if (add_i64_overflows(stream->length, data->size, &required)) return -1;
        if (!ensure_capacity(stream, required)) return -1;
        memcpy(stream->data + stream->length, data->data, (size_t)data->size);
        stream->length += data->size;
        return data->size;
    }

    FileStream *file_stream = as_file(*stream_value, STREAM_KIND_FILE_WRITE);
    if (file_stream) {
        if (file_stream->closed || !file_stream->file) return -1;
        if (data->size == 0) return 0;
        if (!data->data) return -1;
        size_t written = fwrite(data->data, 1, (size_t)data->size, file_stream->file);
        if (written != (size_t)data->size) return -1;
        return data->size;
    }

    if (stream_value->kind == STREAM_KIND_PROCESS_STDIN && as_process_handle(*stream_value)) {
        if (data->size == 0) return 0;
        if (!data->data || data->size < 0) return -1;
        int64_t written = 0;
        while (written < data->size) {
            int64_t remaining = data->size - written;
#if defined(_WIN32)
            DWORD chunk = remaining > INT32_MAX ? (DWORD)INT32_MAX : (DWORD)remaining;
            DWORD n = 0;
            if (!WriteFile((HANDLE)(intptr_t)stream_value->handle, data->data + written, chunk, &n, NULL)) {
                return written > 0 ? written : -1;
            }
            if (n == 0) return written > 0 ? written : -1;
#else
            size_t chunk = remaining > (int64_t)(1024 * 1024 * 16) ? (size_t)(1024 * 1024 * 16) : (size_t)remaining;
            ssize_t n = write((int)stream_value->handle, data->data + written, chunk);
            if (n < 0 && errno == EINTR) continue;
            if (n <= 0) return written > 0 ? written : -1;
#endif
            written += (int64_t)n;
        }
        return written;
    }

    stream_socket_t sock = as_tcp_socket(*stream_value);
    if (sock == STREAM_INVALID_SOCKET) return -1;
    if (data->size == 0) return 0;
    if (!data->data || data->size < 0) return -1;
    int64_t written = 0;
    while (written < data->size) {
        int64_t remaining = data->size - written;
#if defined(_WIN32)
        int chunk = remaining > INT32_MAX ? INT32_MAX : (int)remaining;
        int n = send(sock, (const char *)data->data + written, chunk, 0);
#else
        size_t chunk = remaining > (int64_t)(1024 * 1024 * 16) ? (size_t)(1024 * 1024 * 16) : (size_t)remaining;
        ssize_t n = send(sock, data->data + written, chunk, 0);
#endif
        if (n <= 0) return written > 0 ? written : -1;
        written += (int64_t)n;
    }
    return written;
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
    int64_t copied = 0;
    while (true) {
        OptBlob chunk = streamRead(src_value, bufferSize);
        if (!chunk.ok) return -1;
        if (chunk.value.size == 0) {
            free(chunk.value.data);
            return copied;
        }
        int64_t written = streamWrite(dst_value, &chunk.value);
        free(chunk.value.data);
        if (written != chunk.value.size) return -1;
        if (copied > INT64_MAX - written) return -1;
        copied += written;
    }
}

bool streamFlush(const Stream *stream_value) {
    MemoryStream *stream = stream_value ? as_memory(*stream_value) : NULL;
    if (stream) return !stream->closed;
    FileStream *file_stream = stream_value ? as_file(*stream_value, STREAM_KIND_FILE_WRITE) : NULL;
    if (file_stream) {
        if (file_stream->closed || !file_stream->file) return false;
        return fflush(file_stream->file) == 0;
    }
    if (stream_value && as_process_handle(*stream_value)) return true;
    stream_socket_t sock = stream_value ? as_tcp_socket(*stream_value) : STREAM_INVALID_SOCKET;
    return sock != STREAM_INVALID_SOCKET;
}

bool streamClose(const Stream *stream_value) {
    MemoryStream *stream = stream_value ? as_memory(*stream_value) : NULL;
    if (stream) {
        if (stream->closed) return false;
        stream->closed = true;
        free(stream->data);
        stream->data = NULL;
        stream->length = 0;
        stream->capacity = 0;
        stream->cursor = 0;
        // Stream 是按值传递的句柄；保留 wrapper 作为关闭标记，避免旧句柄再次使用时读已释放内存。
        return true;
    }

    if (!stream_value || stream_value->handle == 0) return false;
    FileStream *file_stream = NULL;
    if (stream_value->kind == STREAM_KIND_FILE_READ) {
        file_stream = as_file(*stream_value, STREAM_KIND_FILE_READ);
    } else if (stream_value->kind == STREAM_KIND_FILE_WRITE) {
        file_stream = as_file(*stream_value, STREAM_KIND_FILE_WRITE);
    }
    if (file_stream) {
        if (file_stream->closed || !file_stream->file) return false;
        file_stream->closed = true;
        bool ok = fclose(file_stream->file) == 0;
        file_stream->file = NULL;
        // 见内存流分支：关闭后旧 Stream 值应稳定返回失败，而不是悬垂指针。
        return ok;
    }

    if (as_process_handle(*stream_value)) {
#if defined(_WIN32)
        return CloseHandle((HANDLE)(intptr_t)stream_value->handle) != 0;
#else
        return close((int)stream_value->handle) == 0;
#endif
    }

    stream_socket_t sock = as_tcp_socket(*stream_value);
    if (sock == STREAM_INVALID_SOCKET) return false;
    return stream_close_socket(sock) == 0;
}
