// EzLang std/test 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int32_t g_passed = 0;
static int32_t g_failed = 0;
static int32_t g_skipped = 0;

static void fail_now(const char *msg) {
    g_failed += 1;
    fprintf(stderr, "test failed: %s\n", msg ? msg : "assertion failed");
    abort();
}

void testAssert(bool condition, const char *msg) {
    if (!condition) fail_now(msg);
    g_passed += 1;
}

void testEqualI64(int64_t actual, int64_t expected, const char *msg) {
    if (actual != expected) {
        char buffer[256];
        snprintf(buffer, sizeof(buffer), "%s: expected %lld, got %lld", msg ? msg : "not equal", (long long)expected, (long long)actual);
        fail_now(buffer);
    }
    g_passed += 1;
}

void testNotEqualI64(int64_t actual, int64_t expected, const char *msg) {
    if (actual == expected) {
        char buffer[256];
        snprintf(buffer, sizeof(buffer), "%s: unexpected %lld", msg ? msg : "equal", (long long)actual);
        fail_now(buffer);
    }
    g_passed += 1;
}

void testEqualStr(const char *actual, const char *expected, const char *msg) {
    const char *a = actual ? actual : "";
    const char *e = expected ? expected : "";
    if (strcmp(a, e) != 0) {
        char buffer[512];
        snprintf(buffer, sizeof(buffer), "%s: expected '%s', got '%s'", msg ? msg : "not equal", e, a);
        fail_now(buffer);
    }
    g_passed += 1;
}

void testSkip(const char *msg) {
    g_skipped += 1;
    fprintf(stderr, "test skipped: %s\n", msg ? msg : "");
}

void testRegister(const char *name) {
    (void)name;
}

int32_t testPassed(void) { return g_passed; }
int32_t testFailed(void) { return g_failed; }
int32_t testSkipped(void) { return g_skipped; }

void testReset(void) {
    g_passed = 0;
    g_failed = 0;
    g_skipped = 0;
}
