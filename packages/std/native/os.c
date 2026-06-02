// EzLang std/os 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <direct.h>
#include <process.h>
#include <shellapi.h>
#include <windows.h>
#define getcwd _getcwd
#else
#include <unistd.h>
#endif

#if defined(__APPLE__)
#include <crt_externs.h>
#include <TargetConditionals.h>
#endif

typedef struct {
    char ***pages;
    int64_t length;
    int64_t capacity;
    int64_t page_count;
} StrList;

typedef struct {
    bool ok;
    const char *value;
} OptStr;

static char *ez_strdup_range(const char *src, size_t len) {
    char *out = (char *)malloc(len + 1);
    if (!out) return NULL;
    if (len > 0 && src) memcpy(out, src, len);
    out[len] = '\0';
    return out;
}

static char *ez_strdup_safe(const char *src) {
    if (!src) src = "";
    return ez_strdup_range(src, strlen(src));
}

static StrList ez_make_str_list(char **items, size_t count) {
    int64_t page_count = count == 0 ? 0 : (int64_t)((count + 7) / 8);
    char ***pages = page_count == 0 ? NULL : (char ***)calloc((size_t)page_count, sizeof(char **));
    if (page_count > 0 && !pages) return (StrList){0};
    for (int64_t page = 0; page < page_count; ++page) {
        pages[page] = (char **)calloc(8, sizeof(char *));
        if (!pages[page]) continue;
        for (int64_t offset = 0; offset < 8; ++offset) {
            size_t idx = (size_t)(page * 8 + offset);
            pages[page][offset] = idx < count ? items[idx] : NULL;
        }
    }
    return (StrList){pages, (int64_t)count, page_count * 8, page_count};
}

#if defined(_WIN32)
static char *ez_wide_to_utf8(const wchar_t *value) {
    if (!value) return ez_strdup_safe("");
    int needed = WideCharToMultiByte(CP_UTF8, 0, value, -1, NULL, 0, NULL, NULL);
    if (needed <= 0) return ez_strdup_safe("");
    char *out = (char *)malloc((size_t)needed);
    if (!out) return NULL;
    WideCharToMultiByte(CP_UTF8, 0, value, -1, out, needed, NULL, NULL);
    return out;
}
#endif

#if !defined(_WIN32) && !defined(__APPLE__)
static StrList ez_linux_args(void) {
    FILE *file = fopen("/proc/self/cmdline", "rb");
    if (!file) return (StrList){0};
    char *buffer = NULL;
    size_t len = 0;
    char chunk[256];
    size_t n = 0;
    while ((n = fread(chunk, 1, sizeof(chunk), file)) > 0) {
        char *next = (char *)realloc(buffer, len + n);
        if (!next) {
            free(buffer);
            fclose(file);
            return (StrList){0};
        }
        buffer = next;
        memcpy(buffer + len, chunk, n);
        len += n;
    }
    fclose(file);
    if (!buffer || len == 0) {
        free(buffer);
        return (StrList){0};
    }

    size_t count = 0;
    for (size_t i = 0; i < len; ++i) {
        if (buffer[i] == '\0') count++;
    }
    if (buffer[len - 1] != '\0') count++;
    char **items = (char **)calloc(count, sizeof(char *));
    if (!items) {
        free(buffer);
        return (StrList){0};
    }
    size_t start = 0;
    size_t item = 0;
    for (size_t i = 0; i <= len; ++i) {
        if (i == len || buffer[i] == '\0') {
            items[item++] = ez_strdup_range(buffer + start, i - start);
            start = i + 1;
        }
    }
    free(buffer);
    StrList result = ez_make_str_list(items, item);
    free(items);
    return result;
}
#endif

StrList args(void) {
#if defined(_WIN32)
    int argc = 0;
    wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!argv || argc <= 0) return (StrList){0};
    char **items = (char **)calloc((size_t)argc, sizeof(char *));
    if (!items) {
        LocalFree(argv);
        return (StrList){0};
    }
    for (int i = 0; i < argc; ++i) items[i] = ez_wide_to_utf8(argv[i]);
    LocalFree(argv);
    StrList result = ez_make_str_list(items, (size_t)argc);
    free(items);
    return result;
#elif defined(__APPLE__)
    int argc = *_NSGetArgc();
    char **argv = *_NSGetArgv();
    if (argc <= 0 || !argv) return (StrList){0};
    char **items = (char **)calloc((size_t)argc, sizeof(char *));
    if (!items) return (StrList){0};
    for (int i = 0; i < argc; ++i) items[i] = ez_strdup_safe(argv[i]);
    StrList result = ez_make_str_list(items, (size_t)argc);
    free(items);
    return result;
#elif defined(__linux__)
    return ez_linux_args();
#else
    return (StrList){0};
#endif
}

OptStr env(const char *key) {
    const char *value = getenv(key);
    return value ? (OptStr){true, value} : (OptStr){false, NULL};
}

bool setEnv(const char *key, const char *value) {
#if defined(_WIN32)
    return _putenv_s(key, value) == 0;
#else
    return setenv(key, value, 1) == 0;
#endif
}

const char *cwd(void) {
    char *buffer = (char *)malloc(4096);
    if (!buffer) return NULL;
    if (getcwd(buffer, 4096) == NULL) {
        free(buffer);
        return NULL;
    }
    return buffer;
}

void exit(int32_t code) {
    _Exit(code);
}

int32_t pid(void) {
#if defined(_WIN32)
    return (int32_t)_getpid();
#else
    return (int32_t)getpid();
#endif
}

const char *platform(void) {
#if defined(_WIN32)
    return "windows";
#elif defined(__ANDROID__)
    return "android";
#elif defined(__APPLE__) && TARGET_OS_IPHONE
    return "ios";
#elif defined(__APPLE__)
    return "macos";
#else
    return "linux";
#endif
}

const char *arch(void) {
#if defined(__aarch64__) || defined(_M_ARM64)
    return "aarch64";
#elif defined(__x86_64__) || defined(_M_X64)
    return "x86_64";
#else
    return "unknown";
#endif
}
