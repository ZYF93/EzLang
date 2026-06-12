// EzLang std/debug 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(__APPLE__)
#include <TargetConditionals.h>
#endif

#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <dbghelp.h>
#define EZ_DEBUG_HAS_WINDOWS_STACK 1
#define EZ_DEBUG_HAS_UNWIND 0
#elif defined(__ANDROID__) || (defined(__APPLE__) && TARGET_OS_IPHONE)
#include <unwind.h>
#define EZ_DEBUG_HAS_EXECINFO 0
#define EZ_DEBUG_HAS_UNWIND 1
#else
#include <execinfo.h>
#define EZ_DEBUG_HAS_EXECINFO 1
#define EZ_DEBUG_HAS_UNWIND 0
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

#if EZ_DEBUG_HAS_UNWIND
static bool ez_append_text(char **out, size_t *len, size_t *cap, const char *text) {
    if (!out || !len || !cap || !text) return false;
    size_t text_len = strlen(text);
    if (*len + text_len + 1 < *len) return false;
    if (*len + text_len + 1 > *cap) {
        size_t next = *cap ? *cap : 256;
        while (*len + text_len + 1 > next) {
            if (next > ((size_t)-1) / 2) return false;
            next *= 2;
        }
        char *grown = (char *)realloc(*out, next);
        if (!grown) return false;
        *out = grown;
        *cap = next;
    }
    memcpy(*out + *len, text, text_len + 1);
    *len += text_len;
    return true;
}

typedef struct {
    uintptr_t frames[32];
    int count;
} EzUnwindStack;

static _Unwind_Reason_Code ez_debug_unwind_frame(struct _Unwind_Context *context, void *arg) {
    EzUnwindStack *stack = (EzUnwindStack *)arg;
    if (!stack || stack->count >= 32) return _URC_END_OF_STACK;
    uintptr_t ip = (uintptr_t)_Unwind_GetIP(context);
    if (ip != 0) stack->frames[stack->count++] = ip;
    return _URC_NO_REASON;
}
#endif

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
#elif defined(__APPLE__) && TARGET_OS_IPHONE
    return ez_strdup_safe("ezlang native/ios");
#elif defined(__APPLE__)
    return ez_strdup_safe("ezlang native/macos");
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
#if defined(EZ_DEBUG_HAS_WINDOWS_STACK)
    void *frames[32];
    USHORT count = CaptureStackBackTrace(0, 32, frames, NULL);
    if (count == 0) return (OptStr){false, NULL};

    HANDLE process = GetCurrentProcess();
    if (!SymInitialize(process, NULL, TRUE)) return (OptStr){false, NULL};

    const size_t symbol_size = sizeof(SYMBOL_INFO) + (MAX_SYM_NAME * sizeof(char));
    SYMBOL_INFO *symbol = (SYMBOL_INFO *)calloc(1, symbol_size);
    if (!symbol) {
        SymCleanup(process);
        return (OptStr){false, NULL};
    }
    symbol->MaxNameLen = MAX_SYM_NAME;
    symbol->SizeOfStruct = sizeof(SYMBOL_INFO);

    size_t cap = 1024;
    size_t len = 0;
    char *out = (char *)malloc(cap);
    if (!out) {
        free(symbol);
        SymCleanup(process);
        return (OptStr){false, NULL};
    }
    out[0] = '\0';

    for (USHORT i = 0; i < count; ++i) {
        DWORD64 addr = (DWORD64)(uintptr_t)frames[i];
        char line[512];
        if (SymFromAddr(process, addr, NULL, symbol)) {
            snprintf(line, sizeof(line), "%u: %s + 0x%llx\n", (unsigned)i, symbol->Name,
                     (unsigned long long)(addr - symbol->Address));
        } else {
            snprintf(line, sizeof(line), "%u: 0x%llx\n", (unsigned)i, (unsigned long long)addr);
        }
        size_t line_len = strlen(line);
        if (len + line_len + 1 > cap) {
            size_t new_cap = cap * 2;
            while (len + line_len + 1 > new_cap) new_cap *= 2;
            char *grown = (char *)realloc(out, new_cap);
            if (!grown) {
                free(out);
                free(symbol);
                SymCleanup(process);
                return (OptStr){false, NULL};
            }
            out = grown;
            cap = new_cap;
        }
        memcpy(out + len, line, line_len + 1);
        len += line_len;
    }
    free(symbol);
    SymCleanup(process);
    return (OptStr){true, out};
#elif EZ_DEBUG_HAS_EXECINFO
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
#elif EZ_DEBUG_HAS_UNWIND
    EzUnwindStack stack = {0};
    _Unwind_Backtrace(ez_debug_unwind_frame, &stack);
    if (stack.count <= 0) return (OptStr){false, NULL};
    char *out = NULL;
    size_t len = 0;
    size_t cap = 0;
    for (int i = 0; i < stack.count; ++i) {
        char line[64];
        snprintf(line, sizeof(line), "%d: 0x%llx\n", i, (unsigned long long)stack.frames[i]);
        if (!ez_append_text(&out, &len, &cap, line)) {
            free(out);
            return (OptStr){false, NULL};
        }
    }
    return (OptStr){true, out};
#else
    return (OptStr){false, NULL};
#endif
}
