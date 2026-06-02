// EzLang std/math 原生封装层

#include <float.h>
#include <limits.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>

typedef struct { bool ok; int32_t value; } OptI32;
typedef struct { bool ok; int64_t value; } OptI64;

int32_t mathAbsI32(int32_t value) {
    return value == INT32_MIN ? INT32_MAX : (value < 0 ? -value : value);
}

int64_t mathAbsI64(int64_t value) {
    return value == INT64_MIN ? INT64_MAX : (value < 0 ? -value : value);
}

int32_t mathMinI32(int32_t a, int32_t b) { return a < b ? a : b; }
int32_t mathMaxI32(int32_t a, int32_t b) { return a > b ? a : b; }

int32_t mathClampI32(int32_t value, int32_t min_value, int32_t max_value) {
    if (min_value > max_value) {
        int32_t tmp = min_value;
        min_value = max_value;
        max_value = tmp;
    }
    if (value < min_value) return min_value;
    if (value > max_value) return max_value;
    return value;
}

int64_t mathGcdI64(int64_t a, int64_t b) {
    uint64_t x = a < 0 ? (uint64_t)(-(a + 1)) + 1 : (uint64_t)a;
    uint64_t y = b < 0 ? (uint64_t)(-(b + 1)) + 1 : (uint64_t)b;
    while (y != 0) {
        uint64_t r = x % y;
        x = y;
        y = r;
    }
    return x > (uint64_t)INT64_MAX ? INT64_MAX : (int64_t)x;
}

int64_t mathLcmI64(int64_t a, int64_t b) {
    if (a == 0 || b == 0) return 0;
    int64_t gcd = mathGcdI64(a, b);
    if (gcd == 0) return 0;
    int64_t reduced = a / gcd;
#if defined(__has_builtin)
#if __has_builtin(__builtin_mul_overflow)
    int64_t result = 0;
    if (__builtin_mul_overflow(reduced, b, &result)) return INT64_MAX;
    return mathAbsI64(result);
#endif
#endif
    if (reduced != 0 && (b > INT64_MAX / reduced || b < INT64_MIN / reduced)) return INT64_MAX;
    return mathAbsI64(reduced * b);
}

double mathSqrt(double value) { return sqrt(value); }
double mathPow(double base, double exp) { return pow(base, exp); }
double mathSin(double value) { return sin(value); }
double mathCos(double value) { return cos(value); }
double mathTan(double value) { return tan(value); }
double mathLog(double value) { return log(value); }
double mathExp(double value) { return exp(value); }
double mathFloor(double value) { return floor(value); }
double mathCeil(double value) { return ceil(value); }
double mathRound(double value) { return round(value); }
bool mathIsNaN(double value) { return isnan(value); }
bool mathIsInf(double value) { return isinf(value); }

OptI64 mathAddI64Checked(int64_t a, int64_t b) {
    int64_t result = 0;
#if defined(__has_builtin)
#if __has_builtin(__builtin_add_overflow)
    if (__builtin_add_overflow(a, b, &result)) return (OptI64){false, 0};
    return (OptI64){true, result};
#endif
#endif
    if ((b > 0 && a > INT64_MAX - b) || (b < 0 && a < INT64_MIN - b)) return (OptI64){false, 0};
    return (OptI64){true, a + b};
}

OptI64 mathSubI64Checked(int64_t a, int64_t b) {
    int64_t result = 0;
#if defined(__has_builtin)
#if __has_builtin(__builtin_sub_overflow)
    if (__builtin_sub_overflow(a, b, &result)) return (OptI64){false, 0};
    return (OptI64){true, result};
#endif
#endif
    if ((b < 0 && a > INT64_MAX + b) || (b > 0 && a < INT64_MIN + b)) return (OptI64){false, 0};
    return (OptI64){true, a - b};
}

OptI64 mathMulI64Checked(int64_t a, int64_t b) {
    int64_t result = 0;
#if defined(__has_builtin)
#if __has_builtin(__builtin_mul_overflow)
    if (__builtin_mul_overflow(a, b, &result)) return (OptI64){false, 0};
    return (OptI64){true, result};
#endif
#endif
    if (a == 0 || b == 0) return (OptI64){true, 0};
    if (a == -1 && b == INT64_MIN) return (OptI64){false, 0};
    if (b == -1 && a == INT64_MIN) return (OptI64){false, 0};
    int64_t result_abs = mathAbsI64(a);
    int64_t b_abs = mathAbsI64(b);
    if (result_abs > INT64_MAX / b_abs) return (OptI64){false, 0};
    return (OptI64){true, a * b};
}

OptI64 mathDivI64Checked(int64_t a, int64_t b) {
    if (b == 0 || (a == INT64_MIN && b == -1)) return (OptI64){false, 0};
    return (OptI64){true, a / b};
}

OptI32 mathF64ToI32(double value) {
    if (!isfinite(value) || value < (double)INT32_MIN || value > (double)INT32_MAX) return (OptI32){false, 0};
    return (OptI32){true, (int32_t)value};
}

OptI64 mathF64ToI64(double value) {
    if (!isfinite(value) || value < (double)INT64_MIN || value > (double)INT64_MAX) return (OptI64){false, 0};
    return (OptI64){true, (int64_t)value};
}

double mathI64ToF64(int64_t value) {
    return (double)value;
}
