// EzLang std/io 原生封装层
// 这些函数实现 EzLang 标准库 ABI，再在内部调用 C 标准库或平台 API。

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(__ANDROID__)
#include <android/log.h>
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
#if defined(__ANDROID__) || (defined(__APPLE__) && TARGET_OS_IPHONE)
    return (OptStr){false, NULL};
#else
    static char buffer[4096];
    if (fgets(buffer, sizeof(buffer), stdin) == NULL) {
        return (OptStr){false, NULL};
    }
    size_t len = strlen(buffer);
    if (len > 0 && buffer[len - 1] == '\n') {
        buffer[len - 1] = '\0';
    }
    return (OptStr){true, buffer};
#endif
}
