// EzLang std/log 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#if defined(__ANDROID__)
#include <android/log.h>
#endif

#if defined(__APPLE__)
#include <TargetConditionals.h>
#if TARGET_OS_IPHONE
#include <os/log.h>
#endif
#endif

#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/time.h>
#endif

typedef struct {
    char ***pages;
    int64_t length;
    int64_t capacity;
    int64_t page_count;
} StrList;

typedef struct {
    int32_t minLevel;
    int32_t target;
    bool includeTimestamp;
    bool includeLocation;
} LogConfig;

static LogConfig ez_log_config = {2, 0, true, true};
static FILE *ez_log_file = NULL;

enum {
    EZ_LOG_TARGET_STDERR = 0,
    EZ_LOG_TARGET_STDOUT = 1,
    EZ_LOG_TARGET_CONSOLE = 2,
    EZ_LOG_TARGET_FILE = 3,
};

static const char *ez_level_name(int32_t level) {
    switch (level) {
        case 0: return "TRACE";
        case 1: return "DEBUG";
        case 2: return "INFO";
        case 3: return "WARN";
        case 4: return "ERROR";
        default: return "LOG";
    }
}

static FILE *ez_log_stream(void) {
    if (ez_log_config.target == EZ_LOG_TARGET_STDOUT) return stdout;
    if (ez_log_config.target == EZ_LOG_TARGET_FILE && ez_log_file) return ez_log_file;
    return stderr;
}

static void ez_log_close_file(void) {
    if (ez_log_file) {
        fclose(ez_log_file);
        ez_log_file = NULL;
    }
}

static int64_t ez_timestamp_ms(void) {
#if defined(_WIN32)
    FILETIME ft;
    GetSystemTimeAsFileTime(&ft);
    uint64_t ticks = ((uint64_t)ft.dwHighDateTime << 32) | ft.dwLowDateTime;
    return (int64_t)((ticks - 116444736000000000ULL) / 10000ULL);
#else
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (int64_t)tv.tv_sec * 1000 + (int64_t)tv.tv_usec / 1000;
#endif
}

static const char *ez_list_get(const StrList *items, int64_t index) {
    if (!items || index < 0 || index >= items->length || !items->pages || items->page_count <= 0) return "";
    int64_t page = index / 8;
    int64_t offset = index % 8;
    if (page >= items->page_count || !items->pages[page]) return "";
    return items->pages[page][offset] ? items->pages[page][offset] : "";
}

static void ez_log_write_impl(int32_t level, const char *msg, const char *file, int32_t line, int32_t column, const StrList *fields) {
    if (level < ez_log_config.minLevel) return;
    FILE *out = ez_log_stream();
    if (ez_log_config.includeTimestamp) fprintf(out, "%lld ", (long long)ez_timestamp_ms());
    fprintf(out, "%s %s", ez_level_name(level), msg ? msg : "");
    if (ez_log_config.includeLocation && file && *file) fprintf(out, " @ %s:%d:%d", file, line, column);
    for (int64_t i = 0; fields && i + 1 < fields->length; i += 2) {
        fprintf(out, " %s=%s", ez_list_get(fields, i), ez_list_get(fields, i + 1));
    }
    fputc('\n', out);
    fflush(out);

#if defined(__ANDROID__)
    if (ez_log_config.target != EZ_LOG_TARGET_FILE) {
        int android_level = level >= 4 ? ANDROID_LOG_ERROR : (level >= 3 ? ANDROID_LOG_WARN : ANDROID_LOG_INFO);
        __android_log_write(android_level, "EzLang", msg ? msg : "");
    }
#elif defined(__APPLE__) && TARGET_OS_IPHONE
    if (ez_log_config.target != EZ_LOG_TARGET_FILE) {
        os_log_type_t os_level = level >= 4 ? OS_LOG_TYPE_ERROR : (level >= 3 ? OS_LOG_TYPE_DEFAULT : OS_LOG_TYPE_INFO);
        os_log_with_type(OS_LOG_DEFAULT, os_level, "%{public}s", msg ? msg : "");
    }
#endif
}

LogConfig logDefaultConfig(void) {
    return (LogConfig){2, 0, true, true};
}

void logConfigure(const LogConfig *config) {
    if (!config) return;
    if (config->target != EZ_LOG_TARGET_FILE) ez_log_close_file();
    ez_log_config = *config;
}

void logSetLevel(int32_t level) {
    ez_log_config.minLevel = level;
}

bool logSetFile(const char *path) {
    if (!path || !*path) return false;
    FILE *next = fopen(path, "a");
    if (!next) return false;
    ez_log_close_file();
    ez_log_file = next;
    ez_log_config.target = EZ_LOG_TARGET_FILE;
    return true;
}

void logWrite(int32_t level, const char *msg) {
    ez_log_write_impl(level, msg, NULL, 0, 0, NULL);
}

void logWriteFields(int32_t level, const char *msg, const StrList *fields) {
    ez_log_write_impl(level, msg, NULL, 0, 0, fields);
}

void logWriteAt(int32_t level, const char *msg, const char *file, int32_t line, int32_t column, const StrList *fields) {
    ez_log_write_impl(level, msg, file, line, column, fields);
}

void logTraceMsg(const char *msg) { logWrite(0, msg); }
void logDebugMsg(const char *msg) { logWrite(1, msg); }
void logInfoMsg(const char *msg) { logWrite(2, msg); }
void logWarnMsg(const char *msg) { logWrite(3, msg); }
void logErrorMsg(const char *msg) { logWrite(4, msg); }
