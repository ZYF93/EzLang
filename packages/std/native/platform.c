// EzLang std/platform 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <limits.h>
#include <stdlib.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <unistd.h>
#if defined(__APPLE__)
#include <TargetConditionals.h>
#include <sys/sysctl.h>
#endif
#endif

const char *platformOS(void) {
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

const char *platformArch(void) {
#if defined(__wasm32__)
    return "wasm32";
#elif defined(__aarch64__) || defined(_M_ARM64)
    return "aarch64";
#elif defined(__x86_64__) || defined(_M_X64)
    return "x86_64";
#elif defined(__i386__) || defined(_M_IX86)
    return "x86";
#else
    return "unknown";
#endif
}

bool platformIsLittleEndian(void) {
    uint16_t value = 1;
    return *((uint8_t *)&value) == 1;
}

int32_t platformPointerBits(void) {
    return (int32_t)(sizeof(void *) * 8);
}

int64_t platformPageSize(void) {
#if defined(_WIN32)
    SYSTEM_INFO info;
    GetSystemInfo(&info);
    return (int64_t)info.dwPageSize;
#elif defined(_SC_PAGESIZE)
    long value = sysconf(_SC_PAGESIZE);
    return value > 0 ? (int64_t)value : -1;
#else
    return -1;
#endif
}

int32_t platformCpuCount(void) {
#if defined(_WIN32)
    SYSTEM_INFO info;
    GetSystemInfo(&info);
    return (int32_t)info.dwNumberOfProcessors;
#elif defined(_SC_NPROCESSORS_ONLN)
    long value = sysconf(_SC_NPROCESSORS_ONLN);
    return value > 0 ? (int32_t)value : 1;
#else
    return 1;
#endif
}

int64_t platformMemoryLimit(void) {
#if defined(_WIN32)
    MEMORYSTATUSEX status;
    status.dwLength = sizeof(status);
    if (GlobalMemoryStatusEx(&status)) return (int64_t)status.ullTotalPhys;
    return -1;
#elif defined(__APPLE__)
    int64_t value = -1;
    size_t size = sizeof(value);
    if (sysctlbyname("hw.memsize", &value, &size, NULL, 0) == 0) return value;
    return -1;
#elif defined(_SC_PHYS_PAGES) && defined(_SC_PAGESIZE)
    long pages = sysconf(_SC_PHYS_PAGES);
    long page_size = sysconf(_SC_PAGESIZE);
    if (pages <= 0 || page_size <= 0) return -1;
    if ((uint64_t)pages > (uint64_t)INT64_MAX / (uint64_t)page_size) return -1;
    return (int64_t)pages * (int64_t)page_size;
#else
    return -1;
#endif
}

bool platformHasThreads(void) {
    return true;
}

bool platformHasFileSystem(void) {
    return true;
}

bool platformHasNetwork(void) {
    return true;
}

bool platformHasCrypto(void) {
    return true;
}

bool platformHasDom(void) {
    return false;
}

bool platformHasSubprocess(void) {
#if defined(__APPLE__) && TARGET_OS_IPHONE
    return false;
#else
    return true;
#endif
}
