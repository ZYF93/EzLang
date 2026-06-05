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
    time_t seconds = (time_t)((value ? value->timestamp : ez_time_timestamp_ms()) / 1000);
    struct tm tm_value;
#if defined(_WIN32)
    gmtime_s(&tm_value, &seconds);
#else
    gmtime_r(&seconds, &tm_value);
#endif
    return tm_value;
}

int32_t getYear(const Date *value) {
    struct tm tm_value = ez_time_tm(value);
    return tm_value.tm_year + 1900;
}

int32_t getMonth(const Date *value) {
    struct tm tm_value = ez_time_tm(value);
    return tm_value.tm_mon + 1;
}

int32_t getDay(const Date *value) {
    struct tm tm_value = ez_time_tm(value);
    return tm_value.tm_mday;
}

int32_t getHour(const Date *value) {
    struct tm tm_value = ez_time_tm(value);
    return tm_value.tm_hour;
}

int32_t getMinute(const Date *value) {
    struct tm tm_value = ez_time_tm(value);
    return tm_value.tm_min;
}

int32_t getSecond(const Date *value) {
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

void add(Date *value, const OptI32 *year, const OptI32 *month, const OptI32 *day,
         const OptI32 *hour, const OptI32 *minute, const OptI32 *second) {
    ez_time_shift(value, year, month, day, hour, minute, second, 1);
}

void sub(Date *value, const OptI32 *year, const OptI32 *month, const OptI32 *day,
         const OptI32 *hour, const OptI32 *minute, const OptI32 *second) {
    ez_time_shift(value, year, month, day, hour, minute, second, -1);
}

static void ez_append_padded(char *out, size_t out_size, size_t *used, int value, int width) {
    if (*used >= out_size) return;
    int written = snprintf(out + *used, out_size - *used, "%0*d", width, value);
    if (written < 0) return;
    *used += (size_t)written;
    if (*used >= out_size) {
        out[out_size - 1] = '\0';
        *used = out_size - 1;
    }
}

static void ez_append_text(char *out, size_t out_size, size_t *used, const char *text, size_t len) {
    if (*used >= out_size) return;
    size_t remaining = out_size - *used - 1;
    if (len > remaining) len = remaining;
    memcpy(out + *used, text, len);
    *used += len;
    out[*used] = '\0';
}

static const char *ez_format_named_token(char *out, size_t out_size, size_t *used,
                                         const char *cursor, const struct tm *tm_value) {
    if (strncmp(cursor, "YYYY", 4) == 0) {
        ez_append_padded(out, out_size, used, tm_value->tm_year + 1900, 4);
        return cursor + 4;
    }
    if (strncmp(cursor, "MM", 2) == 0) {
        ez_append_padded(out, out_size, used, tm_value->tm_mon + 1, 2);
        return cursor + 2;
    }
    if (strncmp(cursor, "DD", 2) == 0) {
        ez_append_padded(out, out_size, used, tm_value->tm_mday, 2);
        return cursor + 2;
    }
    if (strncmp(cursor, "HH", 2) == 0) {
        ez_append_padded(out, out_size, used, tm_value->tm_hour, 2);
        return cursor + 2;
    }
    if (strncmp(cursor, "SS", 2) == 0) {
        ez_append_padded(out, out_size, used, tm_value->tm_sec, 2);
        return cursor + 2;
    }
    ez_append_text(out, out_size, used, cursor, 1);
    return cursor + 1;
}

static const char *ez_format_percent_token(char *out, size_t out_size, size_t *used,
                                           const char *cursor, const struct tm *tm_value) {
    char buffer[16];
    if (cursor[0] != '%' || cursor[1] == '\0') {
        ez_append_text(out, out_size, used, cursor, 1);
        return cursor + 1;
    }
    switch (cursor[1]) {
        case 'Y':
            ez_append_padded(out, out_size, used, tm_value->tm_year + 1900, 4);
            break;
        case 'm':
            ez_append_padded(out, out_size, used, tm_value->tm_mon + 1, 2);
            break;
        case 'd':
            ez_append_padded(out, out_size, used, tm_value->tm_mday, 2);
            break;
        case 'H':
            ez_append_padded(out, out_size, used, tm_value->tm_hour, 2);
            break;
        case 'M':
            ez_append_padded(out, out_size, used, tm_value->tm_min, 2);
            break;
        case 'S':
            ez_append_padded(out, out_size, used, tm_value->tm_sec, 2);
            break;
        case '%':
            ez_append_text(out, out_size, used, "%", 1);
            break;
        default:
            buffer[0] = '%';
            buffer[1] = cursor[1];
            buffer[2] = '\0';
            ez_append_text(out, out_size, used, buffer, 2);
            break;
    }
    return cursor + 2;
}

const char *format(const Date *value, const char *fmt) {
    struct tm tm_value = ez_time_tm(value);
    const char *pattern = fmt ? fmt : "%Y-%m-%dT%H:%M:%SZ";
    char *result = (char *)malloc(128);
    if (!result) return NULL;
    size_t used = 0;
    result[0] = '\0';
    const char *cursor = pattern;
    while (*cursor != '\0' && used < 127) {
        if (*cursor == '%') {
            cursor = ez_format_percent_token(result, 128, &used, cursor, &tm_value);
        } else {
            cursor = ez_format_named_token(result, 128, &used, cursor, &tm_value);
        }
    }
    return result;
}
