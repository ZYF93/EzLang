// EzLang std/hash 原生封装层

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

static const uint8_t *ez_blob_data(const Blob *data, size_t *size) {
    if (!data || data->size <= 0 || !data->data || (uint64_t)data->size > (uint64_t)SIZE_MAX) {
        *size = 0;
        return (const uint8_t *)"";
    }
    *size = (size_t)data->size;
    return data->data;
}

uint32_t hashFnv1a32(const Blob *data) {
    size_t size = 0;
    const uint8_t *bytes = ez_blob_data(data, &size);
    uint32_t hash = 2166136261u;
    for (size_t i = 0; i < size; ++i) {
        hash ^= bytes[i];
        hash *= 16777619u;
    }
    return hash;
}

uint64_t hashFnv1a64(const Blob *data) {
    size_t size = 0;
    const uint8_t *bytes = ez_blob_data(data, &size);
    uint64_t hash = 14695981039346656037ULL;
    for (size_t i = 0; i < size; ++i) {
        hash ^= bytes[i];
        hash *= 1099511628211ULL;
    }
    return hash;
}

uint32_t hashStrFnv1a32(const char *s) {
    Blob data = {(uint8_t *)(s ? s : ""), (int64_t)strlen(s ? s : "")};
    return hashFnv1a32(&data);
}

uint64_t hashStrFnv1a64(const char *s) {
    Blob data = {(uint8_t *)(s ? s : ""), (int64_t)strlen(s ? s : "")};
    return hashFnv1a64(&data);
}

uint64_t hashCombineU64(uint64_t seed, uint64_t value) {
    return seed ^ (value + 0x9E3779B97F4A7C15ULL + (seed << 6) + (seed >> 2));
}

uint32_t crc32(const Blob *data) {
    size_t size = 0;
    const uint8_t *bytes = ez_blob_data(data, &size);
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < size; ++i) {
        crc ^= bytes[i];
        for (int bit = 0; bit < 8; ++bit) {
            uint32_t mask = (uint32_t)(-(int32_t)(crc & 1u));
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    return ~crc;
}

uint32_t crc32Str(const char *s) {
    Blob data = {(uint8_t *)(s ? s : ""), (int64_t)strlen(s ? s : "")};
    return crc32(&data);
}
