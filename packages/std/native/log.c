// EzLang std/log 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

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
    return ez_log_config.target == 1 ? stdout : stderr;
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
}

LogConfig logDefaultConfig(void) {
    return (LogConfig){2, 0, true, true};
}

void logConfigure(const LogConfig *config) {
    if (config) ez_log_config = *config;
}

void logSetLevel(int32_t level) {
    ez_log_config.minLevel = level;
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
