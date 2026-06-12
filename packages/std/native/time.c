// EzLang std/time 原生封装层

#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/time.h>
#endif

#if defined(_WIN32)
#define EZ_ABI_NAME(name)
#else
#define EZ_ABI_NAME(name) __asm__(#name)
#endif

typedef struct {
    int64_t timestamp;
} Date;

typedef struct {
    bool ok;
    int32_t value;
} OptI32;

static int64_t ez_time_timestamp_ms(void);

static time_t ez_time_seconds_floor(int64_t timestamp_ms) {
    int64_t seconds = timestamp_ms / 1000;
    if (timestamp_ms < 0 && (timestamp_ms % 1000) != 0) seconds--;
    return (time_t)seconds;
}

Date now(void) {
    return (Date){ .timestamp = ez_time_timestamp_ms() };
}

static int64_t ez_time_timestamp_ms(void) {
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

int64_t timestamp(void) {
    return ez_time_timestamp_ms();
}

void ez_std_sleep(int64_t ms) EZ_ABI_NAME(sleep);
void ez_std_sleep(int64_t ms) {
    if (ms <= 0) return;
#if defined(_WIN32)
    Sleep((DWORD)ms);
#else
    struct timespec req;
    req.tv_sec = (time_t)(ms / 1000);
    req.tv_nsec = (long)((ms % 1000) * 1000000L);
    while (nanosleep(&req, &req) != 0) {}
#endif
}

static struct tm ez_time_tm(const Date *value) {
    int64_t timestamp_ms = value ? value->timestamp : ez_time_timestamp_ms();
    time_t seconds = ez_time_seconds_floor(timestamp_ms);
    struct tm tm_value;
#if defined(_WIN32)
    gmtime_s(&tm_value, &seconds);
#else
    gmtime_r(&seconds, &tm_value);
#endif
    return tm_value;
}

int32_t dateGetYear(const Date *value) {
    struct tm tm_value = ez_time_tm(value);
    return tm_value.tm_year + 1900;
}

int32_t dateGetMonth(const Date *value) {
    struct tm tm_value = ez_time_tm(value);
    return tm_value.tm_mon + 1;
}

int32_t dateGetDay(const Date *value) {
    struct tm tm_value = ez_time_tm(value);
    return tm_value.tm_mday;
}

int32_t dateGetHour(const Date *value) {
    struct tm tm_value = ez_time_tm(value);
    return tm_value.tm_hour;
}

int32_t dateGetMinute(const Date *value) {
    struct tm tm_value = ez_time_tm(value);
    return tm_value.tm_min;
}

int32_t dateGetSecond(const Date *value) {
    struct tm tm_value = ez_time_tm(value);
    return tm_value.tm_sec;
}

static int32_t ez_opt_i32(const OptI32 *value) {
    return value && value->ok ? value->value : 0;
}

static time_t ez_timegm(struct tm *tm_value) {
#if defined(_WIN32)
    return _mkgmtime(tm_value);
#else
    return timegm(tm_value);
#endif
}

static void ez_time_shift(Date *value, const OptI32 *year, const OptI32 *month, const OptI32 *day,
                          const OptI32 *hour, const OptI32 *minute, const OptI32 *second, int sign) {
    if (!value) return;
    int64_t ms = value->timestamp % 1000;
    if (ms < 0) ms += 1000;
    struct tm tm_value = ez_time_tm(value);
    tm_value.tm_year += sign * ez_opt_i32(year);
    tm_value.tm_mon += sign * ez_opt_i32(month);
    tm_value.tm_mday += sign * ez_opt_i32(day);
    tm_value.tm_hour += sign * ez_opt_i32(hour);
    tm_value.tm_min += sign * ez_opt_i32(minute);
    tm_value.tm_sec += sign * ez_opt_i32(second);
    time_t shifted = ez_timegm(&tm_value);
    value->timestamp = (int64_t)shifted * 1000 + ms;
}

void dateAdd(Date *value, const OptI32 *year, const OptI32 *month, const OptI32 *day,
             const OptI32 *hour, const OptI32 *minute, const OptI32 *second) {
    ez_time_shift(value, year, month, day, hour, minute, second, 1);
}

void dateSub(Date *value, const OptI32 *year, const OptI32 *month, const OptI32 *day,
             const OptI32 *hour, const OptI32 *minute, const OptI32 *second) {
    ez_time_shift(value, year, month, day, hour, minute, second, -1);
}

static bool ez_reserve(char **out, size_t *cap, size_t needed) {
    if (needed < *cap) return true;
    size_t next = *cap ? *cap : 32;
    while (needed >= next) {
        if (next > ((size_t)-1) / 2) {
            next = needed + 1;
            break;
        }
        next *= 2;
    }
    char *grown = (char *)realloc(*out, next);
    if (!grown) return false;
    *out = grown;
    *cap = next;
    return true;
}

static bool ez_append_text(char **out, size_t *cap, size_t *used, const char *text, size_t len) {
    if (!text) len = 0;
    if (len > ((size_t)-1) - *used - 1) return false;
    if (!ez_reserve(out, cap, *used + len + 1)) return false;
    if (len > 0) memcpy(*out + *used, text, len);
    *used += len;
    (*out)[*used] = '\0';
    return true;
}

static bool ez_append_padded(char **out, size_t *cap, size_t *used, int value, int width) {
    char buffer[32];
    int written = snprintf(buffer, sizeof(buffer), "%0*d", width, value);
    if (written < 0) return false;
    return ez_append_text(out, cap, used, buffer, (size_t)written);
}

static const char *ez_format_named_token(char **out, size_t *cap, size_t *used,
                                         const char *cursor, const struct tm *tm_value, bool *ok) {
    if (strncmp(cursor, "YYYY", 4) == 0) {
        *ok = ez_append_padded(out, cap, used, tm_value->tm_year + 1900, 4);
        return cursor + 4;
    }
    if (strncmp(cursor, "MM", 2) == 0) {
        *ok = ez_append_padded(out, cap, used, tm_value->tm_mon + 1, 2);
        return cursor + 2;
    }
    if (strncmp(cursor, "mm", 2) == 0) {
        *ok = ez_append_padded(out, cap, used, tm_value->tm_min, 2);
        return cursor + 2;
    }
    if (strncmp(cursor, "DD", 2) == 0) {
        *ok = ez_append_padded(out, cap, used, tm_value->tm_mday, 2);
        return cursor + 2;
    }
    if (strncmp(cursor, "HH", 2) == 0) {
        *ok = ez_append_padded(out, cap, used, tm_value->tm_hour, 2);
        return cursor + 2;
    }
    if (strncmp(cursor, "SS", 2) == 0) {
        *ok = ez_append_padded(out, cap, used, tm_value->tm_sec, 2);
        return cursor + 2;
    }
    *ok = ez_append_text(out, cap, used, cursor, 1);
    return cursor + 1;
}

static const char *ez_format_percent_token(char **out, size_t *cap, size_t *used,
                                           const char *cursor, const struct tm *tm_value, bool *ok) {
    char buffer[16];
    if (cursor[0] != '%' || cursor[1] == '\0') {
        *ok = ez_append_text(out, cap, used, cursor, 1);
        return cursor + 1;
    }
    switch (cursor[1]) {
        case 'Y':
            *ok = ez_append_padded(out, cap, used, tm_value->tm_year + 1900, 4);
            break;
        case 'm':
            *ok = ez_append_padded(out, cap, used, tm_value->tm_mon + 1, 2);
            break;
        case 'd':
            *ok = ez_append_padded(out, cap, used, tm_value->tm_mday, 2);
            break;
        case 'H':
            *ok = ez_append_padded(out, cap, used, tm_value->tm_hour, 2);
            break;
        case 'M':
            *ok = ez_append_padded(out, cap, used, tm_value->tm_min, 2);
            break;
        case 'S':
            *ok = ez_append_padded(out, cap, used, tm_value->tm_sec, 2);
            break;
        case '%':
            *ok = ez_append_text(out, cap, used, "%", 1);
            break;
        default:
            buffer[0] = '%';
            buffer[1] = cursor[1];
            buffer[2] = '\0';
            *ok = ez_append_text(out, cap, used, buffer, 2);
            break;
    }
    return cursor + 2;
}

const char *__durationToString(int64_t ms) {
    char buffer[32];
    int written = snprintf(buffer, sizeof(buffer), "%lldms", (long long)ms);
    if (written < 0) return NULL;
    char *out = (char *)malloc((size_t)written + 1);
    if (!out) return NULL;
    memcpy(out, buffer, (size_t)written + 1);
    return out;
}

const char *dateFormat(const Date *value, const char *fmt) {
    struct tm tm_value = ez_time_tm(value);
    const char *pattern = fmt ? fmt : "%Y-%m-%dT%H:%M:%SZ";
    size_t cap = strlen(pattern) + 32;
    char *result = (char *)malloc(cap);
    if (!result) return NULL;
    size_t used = 0;
    result[0] = '\0';
    const char *cursor = pattern;
    bool ok = true;
    while (*cursor != '\0' && ok) {
        if (*cursor == '%') {
            cursor = ez_format_percent_token(&result, &cap, &used, cursor, &tm_value, &ok);
        } else {
            cursor = ez_format_named_token(&result, &cap, &used, cursor, &tm_value, &ok);
        }
    }
    if (!ok) {
        free(result);
        return NULL;
    }
    return result;
}
