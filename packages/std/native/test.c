// EzLang std/test 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int32_t g_passed = 0;
static int32_t g_failed = 0;
static int32_t g_skipped = 0;
static char **g_tests = NULL;
static int32_t g_test_count = 0;
static int32_t g_test_capacity = 0;
static const char *g_current_test = NULL;

static char *copy_text(const char *src) {
    if (!src) src = "";
    size_t len = strlen(src);
    char *out = (char *)malloc(len + 1);
    if (!out) return NULL;
    memcpy(out, src, len + 1);
    return out;
}

static void remember_test_name(const char *name) {
    if (g_test_count >= g_test_capacity) {
        int32_t next_capacity = g_test_capacity == 0 ? 8 : g_test_capacity * 2;
        char **next = (char **)realloc(g_tests, (size_t)next_capacity * sizeof(char *));
        if (!next) return;
        g_tests = next;
        g_test_capacity = next_capacity;
    }
    char *copy = copy_text(name);
    if (!copy) return;
    g_tests[g_test_count++] = copy;
    g_current_test = copy;
}

static void fail_now(const char *msg) {
    g_failed += 1;
    if (g_current_test && *g_current_test) {
        fprintf(stderr, "test failed: %s: %s\n", g_current_test, msg ? msg : "assertion failed");
    } else {
        fprintf(stderr, "test failed: %s\n", msg ? msg : "assertion failed");
    }
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
    remember_test_name(name);
}

void testRegisterParam(const char *name, const char *param) {
    const char *safe_name = name ? name : "";
    const char *safe_param = param ? param : "";
    size_t len = strlen(safe_name) + strlen(safe_param) + 4;
    char *full = (char *)malloc(len);
    if (!full) return;
    snprintf(full, len, "%s[%s]", safe_name, safe_param);
    remember_test_name(full);
    free(full);
}

int32_t testCount(void) { return g_test_count; }

const char *testName(int32_t index) {
    if (index < 0 || index >= g_test_count) return "";
    return g_tests[index] ? g_tests[index] : "";
}

int32_t testPassed(void) { return g_passed; }
int32_t testFailed(void) { return g_failed; }
int32_t testSkipped(void) { return g_skipped; }

void testReset(void) {
    g_passed = 0;
    g_failed = 0;
    g_skipped = 0;
    for (int32_t i = 0; i < g_test_count; ++i) {
        free(g_tests[i]);
        g_tests[i] = NULL;
    }
    g_test_count = 0;
    g_current_test = NULL;
}
