// EzLang std/io 原生封装层
// 这些函数实现 EzLang 标准库 ABI，再在内部调用 C 标准库或平台 API。

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(__ANDROID__)
#ifndef __has_include
#define __has_include(path) 0
#endif
#if __has_include(<android/log.h>)
#include <android/log.h>
#else
#define ANDROID_LOG_INFO 4
#define ANDROID_LOG_ERROR 6
extern int __android_log_write(int prio, const char *tag, const char *text);
#endif
#endif

#if defined(__APPLE__)
#include <TargetConditionals.h>
#if TARGET_OS_IPHONE
#include <os/log.h>
#endif
#endif

typedef struct {
    bool ok;
    const char *value;
} OptStr;

static const char *ez_io_msg(const char *msg) {
    return msg ? msg : "";
}

void print(const char *msg) {
#if defined(__ANDROID__)
    __android_log_write(ANDROID_LOG_INFO, "EzLang", ez_io_msg(msg));
#elif defined(__APPLE__) && TARGET_OS_IPHONE
    os_log_with_type(OS_LOG_DEFAULT, OS_LOG_TYPE_INFO, "%{public}s", ez_io_msg(msg));
#else
    fputs(ez_io_msg(msg), stdout);
#endif
}

void println(const char *msg) {
#if defined(__ANDROID__)
    __android_log_write(ANDROID_LOG_INFO, "EzLang", ez_io_msg(msg));
#elif defined(__APPLE__) && TARGET_OS_IPHONE
    os_log_with_type(OS_LOG_DEFAULT, OS_LOG_TYPE_INFO, "%{public}s", ez_io_msg(msg));
#else
    fputs(ez_io_msg(msg), stdout);
    fputc('\n', stdout);
#endif
}

void error(const char *msg) {
#if defined(__ANDROID__)
    __android_log_write(ANDROID_LOG_ERROR, "EzLang", ez_io_msg(msg));
#elif defined(__APPLE__) && TARGET_OS_IPHONE
    os_log_with_type(OS_LOG_DEFAULT, OS_LOG_TYPE_ERROR, "%{public}s", ez_io_msg(msg));
#else
    fputs(ez_io_msg(msg), stderr);
#endif
}

OptStr readLine(void) {
    size_t cap = 128;
    size_t len = 0;
    char *buffer = (char *)malloc(cap);
    if (!buffer) return (OptStr){false, NULL};
    int ch = 0;
    while ((ch = fgetc(stdin)) != EOF) {
        if (ch == '\n') break;
        if (len + 1 >= cap) {
            if (cap > ((size_t)-1) / 2) {
                free(buffer);
                return (OptStr){false, NULL};
            }
            size_t next_cap = cap * 2;
            char *next = (char *)realloc(buffer, next_cap);
            if (!next) {
                free(buffer);
                return (OptStr){false, NULL};
            }
            buffer = next;
            cap = next_cap;
        }
        buffer[len++] = (char)ch;
    }
    if (ch == EOF && len == 0) {
        free(buffer);
        return (OptStr){false, NULL};
    }
    if (len > 0 && buffer[len - 1] == '\r') len--;
    buffer[len] = '\0';
    return (OptStr){true, buffer};
}
