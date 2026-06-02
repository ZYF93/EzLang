// EzLang std/debug 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !defined(_WIN32)
#include <execinfo.h>
#endif

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

typedef struct { bool ok; const char *value; } OptStr;

static char *ez_strdup_safe(const char *src) {
    if (!src) src = "";
    size_t len = strlen(src);
    char *out = (char *)malloc(len + 1);
    if (!out) return NULL;
    memcpy(out, src, len + 1);
    return out;
}

void debugPrint(const char *msg) {
    fputs(msg ? msg : "", stderr);
    fputc('\n', stderr);
}

void debugCrash(const char *msg) {
    debugPrint(msg ? msg : "debug crash");
    abort();
}

void debugAssert(bool condition, const char *msg) {
    if (!condition) debugCrash(msg ? msg : "assertion failed");
}

const char *debugLocation(const char *file, int32_t line, int32_t column) {
    if (!file) file = "";
    size_t len = strlen(file) + 64;
    char *out = (char *)malloc(len);
    if (!out) return NULL;
    snprintf(out, len, "%s:%d:%d", file, line, column);
    return out;
}

const char *debugRuntimeInfo(void) {
#if defined(_WIN32)
    return ez_strdup_safe("ezlang native/windows");
#elif defined(__ANDROID__)
    return ez_strdup_safe("ezlang native/android");
#elif defined(__APPLE__)
    return ez_strdup_safe("ezlang native/apple");
#elif defined(__linux__)
    return ez_strdup_safe("ezlang native/linux");
#else
    return ez_strdup_safe("ezlang native/unknown");
#endif
}

const char *debugHex(const Blob *data) {
    static const char hex[] = "0123456789abcdef";
    if (!data || data->size <= 0 || !data->data) return ez_strdup_safe("");
    size_t size = (size_t)data->size;
    char *out = (char *)malloc(size * 2 + 1);
    if (!out) return NULL;
    for (size_t i = 0; i < size; ++i) {
        out[i * 2] = hex[data->data[i] >> 4];
        out[i * 2 + 1] = hex[data->data[i] & 0x0F];
    }
    out[size * 2] = '\0';
    return out;
}

OptStr debugStack(void) {
#if defined(_WIN32)
    return (OptStr){false, NULL};
#else
    void *frames[32];
    int count = backtrace(frames, 32);
    if (count <= 0) return (OptStr){false, NULL};
    char **symbols = backtrace_symbols(frames, count);
    if (!symbols) return (OptStr){false, NULL};
    size_t len = 1;
    for (int i = 0; i < count; ++i) len += strlen(symbols[i]) + 1;
    char *out = (char *)malloc(len);
    if (!out) {
        free(symbols);
        return (OptStr){false, NULL};
    }
    out[0] = '\0';
    for (int i = 0; i < count; ++i) {
        strcat(out, symbols[i]);
        strcat(out, "\n");
    }
    free(symbols);
    return (OptStr){true, out};
#endif
}
