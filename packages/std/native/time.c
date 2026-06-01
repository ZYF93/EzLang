// EzLang std/time 原生封装层

#include <stdint.h>
#include <time.h>

typedef struct {
    int64_t timestamp;
} Date;

Date now(void) {
    return (Date){ .timestamp = (int64_t)time(NULL) };
}

int64_t timestamp(void) {
    return (int64_t)time(NULL);
}

void sleep(int64_t ms) {
    (void)ms;
}

int32_t getYear(Date value) {
    (void)value;
    return 1970;
}

int32_t getMonth(Date value) {
    (void)value;
    return 1;
}

int32_t getDay(Date value) {
    (void)value;
    return 1;
}

void add(Date value, int32_t year, int32_t month, int32_t day, int32_t hour, int32_t minute, int32_t second) {
    (void)value;
    (void)year;
    (void)month;
    (void)day;
    (void)hour;
    (void)minute;
    (void)second;
}

void sub(Date value, int32_t year, int32_t month, int32_t day, int32_t hour, int32_t minute, int32_t second) {
    (void)value;
    (void)year;
    (void)month;
    (void)day;
    (void)hour;
    (void)minute;
    (void)second;
}

const char *format(Date value, const char *fmt) {
    (void)value;
    return fmt;
}
