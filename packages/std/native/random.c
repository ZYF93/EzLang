// EzLang std/random 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#if defined(_WIN32)
#include <windows.h>
#include <wincrypt.h>
#else
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#if defined(__APPLE__) || defined(__FreeBSD__) || defined(__OpenBSD__) || defined(__NetBSD__)
#include <sys/random.h>
#elif defined(__linux__)
#include <sys/random.h>
#endif
#endif

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

typedef struct {
    uint64_t state;
} RandomSource;

typedef struct { bool ok; Blob value; } OptBlob;
typedef struct { bool ok; uint64_t value; } OptU64;

static uint64_t ez_random_mix_seed(uint64_t seed) {
    uint64_t z = seed + 0x9E3779B97F4A7C15ULL;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static uint64_t ez_random_next(RandomSource *source) {
    if (!source) return ez_random_mix_seed(0);
    uint64_t x = source->state;
    if (x == 0) x = ez_random_mix_seed(0);
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    source->state = x;
    return x * 0x2545F4914F6CDD1DULL;
}

RandomSource randomSeed(uint64_t seed) {
    uint64_t state = ez_random_mix_seed(seed);
    if (state == 0) state = 0x9E3779B97F4A7C15ULL;
    return (RandomSource){state};
}

uint32_t randomNextU32(RandomSource *source) {
    return (uint32_t)(ez_random_next(source) >> 32);
}

uint64_t randomNextU64(RandomSource *source) {
    return ez_random_next(source);
}

int64_t randomRangeI64(RandomSource *source, int64_t min_value, int64_t max_value) {
    if (min_value > max_value) {
        int64_t tmp = min_value;
        min_value = max_value;
        max_value = tmp;
    }
    uint64_t span = (uint64_t)max_value - (uint64_t)min_value + 1ULL;
    if (span == 0) return (int64_t)ez_random_next(source);
    uint64_t limit = UINT64_MAX - (UINT64_MAX % span);
    uint64_t value = 0;
    do {
        value = ez_random_next(source);
    } while (value >= limit);
    return (int64_t)((uint64_t)min_value + (value % span));
}

double randomRangeF64(RandomSource *source, double min_value, double max_value) {
    if (min_value > max_value) {
        double tmp = min_value;
        min_value = max_value;
        max_value = tmp;
    }
    uint64_t raw = ez_random_next(source) >> 11;
    double unit = (double)raw * (1.0 / 9007199254740992.0);
    return min_value + (max_value - min_value) * unit;
}

Blob randomShuffleBytes(RandomSource *source, const Blob *data) {
    if (!data || data->size <= 0 || !data->data) return (Blob){NULL, 0};
    uint8_t *out = (uint8_t *)malloc((size_t)data->size);
    if (!out) return (Blob){NULL, 0};
    for (int64_t i = 0; i < data->size; ++i) out[i] = data->data[i];
    for (int64_t i = data->size - 1; i > 0; --i) {
        int64_t j = randomRangeI64(source, 0, i);
        uint8_t tmp = out[i];
        out[i] = out[j];
        out[j] = tmp;
    }
    return (Blob){out, data->size};
}

static bool ez_random_read_system(uint8_t *data, size_t size) {
    if (size == 0) return true;
    if (!data) return false;
#if defined(_WIN32)
    HCRYPTPROV provider = 0;
    if (!CryptAcquireContext(&provider, NULL, NULL, PROV_RSA_FULL, CRYPT_VERIFYCONTEXT)) return false;
    BOOL ok = CryptGenRandom(provider, (DWORD)size, data);
    CryptReleaseContext(provider, 0);
    return ok != 0;
#elif defined(__APPLE__) || defined(__FreeBSD__) || defined(__OpenBSD__) || defined(__NetBSD__)
    arc4random_buf(data, size);
    return true;
#elif defined(__linux__)
    size_t offset = 0;
    while (offset < size) {
        ssize_t n = getrandom(data + offset, size - offset, 0);
        if (n > 0) {
            offset += (size_t)n;
            continue;
        }
        if (n < 0 && errno == EINTR) continue;
        break;
    }
    if (offset == size) return true;
#endif
#if !defined(_WIN32)
    int fd = open("/dev/urandom", O_RDONLY);
    if (fd < 0) return false;
    size_t fallback_offset = 0;
    while (fallback_offset < size) {
        ssize_t n = read(fd, data + fallback_offset, size - fallback_offset);
        if (n > 0) {
            fallback_offset += (size_t)n;
            continue;
        }
        if (n < 0 && errno == EINTR) continue;
        close(fd);
        return false;
    }
    close(fd);
    return true;
#else
    return false;
#endif
}

OptBlob randomSecureBytes(int64_t size) {
    if (size < 0) return (OptBlob){false, {0}};
    uint8_t *data = size == 0 ? NULL : (uint8_t *)malloc((size_t)size);
    if (size > 0 && !data) return (OptBlob){false, {0}};
    if (!ez_random_read_system(data, (size_t)size)) {
        free(data);
        return (OptBlob){false, {0}};
    }
    return (OptBlob){true, {data, size}};
}

OptBlob randomEntropy(int64_t size) {
    return randomSecureBytes(size);
}

OptU64 randomSecureU64(void) {
    uint64_t value = 0;
    if (!ez_random_read_system((uint8_t *)&value, sizeof(value))) return (OptU64){false, 0};
    return (OptU64){true, value};
}
