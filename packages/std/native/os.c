// EzLang std/os 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>

const char **args(void) {
    return NULL;
}

const char *env(const char *key) {
    return getenv(key);
}

bool setEnv(const char *key, const char *value) {
#if defined(_WIN32)
    return _putenv_s(key, value) == 0;
#else
    return setenv(key, value, 1) == 0;
#endif
}

const char *cwd(void) {
    return ".";
}

void exit(int32_t code) {
    _Exit(code);
}

int32_t pid(void) {
    return 0;
}

const char *platform(void) {
#if defined(_WIN32)
    return "windows";
#elif defined(__APPLE__)
    return "macos";
#elif defined(__ANDROID__)
    return "android";
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
