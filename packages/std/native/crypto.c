// EzLang std/crypto 原生封装层
// 只封装成熟平台库；不可用平台返回空可选值。

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if defined(__APPLE__)
#include <CommonCrypto/CommonCrypto.h>
#endif

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

typedef struct { bool ok; Blob value; } OptBlob;

static const uint8_t *ez_blob_data(const Blob *blob, size_t *size) {
    if (!blob || blob->size < 0 || (blob->size > 0 && !blob->data)) {
        *size = 0;
        return NULL;
    }
    *size = (size_t)blob->size;
    return blob->data;
}

static OptBlob ez_blob_result(uint8_t *data, size_t size) {
    if (!data && size > 0) return (OptBlob){false, {0}};
    return (OptBlob){true, {data, (int64_t)size}};
}

OptBlob cryptoSha256(const Blob *data) {
#if defined(__APPLE__)
    size_t size = 0;
    const uint8_t *bytes = ez_blob_data(data, &size);
    if (!bytes && size > 0) return (OptBlob){false, {0}};
    uint8_t *out = (uint8_t *)malloc(CC_SHA256_DIGEST_LENGTH);
    if (!out) return (OptBlob){false, {0}};
    CC_SHA256(bytes ? bytes : (const uint8_t *)"", (CC_LONG)size, out);
    return ez_blob_result(out, CC_SHA256_DIGEST_LENGTH);
#else
    (void)data;
    return (OptBlob){false, {0}};
#endif
}

OptBlob cryptoSha512(const Blob *data) {
#if defined(__APPLE__)
    size_t size = 0;
    const uint8_t *bytes = ez_blob_data(data, &size);
    if (!bytes && size > 0) return (OptBlob){false, {0}};
    uint8_t *out = (uint8_t *)malloc(CC_SHA512_DIGEST_LENGTH);
    if (!out) return (OptBlob){false, {0}};
    CC_SHA512(bytes ? bytes : (const uint8_t *)"", (CC_LONG)size, out);
    return ez_blob_result(out, CC_SHA512_DIGEST_LENGTH);
#else
    (void)data;
    return (OptBlob){false, {0}};
#endif
}

OptBlob cryptoHmacSha256(const Blob *key, const Blob *data) {
#if defined(__APPLE__)
    size_t key_size = 0;
    size_t data_size = 0;
    const uint8_t *key_bytes = ez_blob_data(key, &key_size);
    const uint8_t *data_bytes = ez_blob_data(data, &data_size);
    if ((!key_bytes && key_size > 0) || (!data_bytes && data_size > 0)) return (OptBlob){false, {0}};
    uint8_t *out = (uint8_t *)malloc(CC_SHA256_DIGEST_LENGTH);
    if (!out) return (OptBlob){false, {0}};
    CCHmac(kCCHmacAlgSHA256, key_bytes ? key_bytes : (const uint8_t *)"", key_size,
           data_bytes ? data_bytes : (const uint8_t *)"", data_size, out);
    return ez_blob_result(out, CC_SHA256_DIGEST_LENGTH);
#else
    (void)key;
    (void)data;
    return (OptBlob){false, {0}};
#endif
}

OptBlob cryptoHmacSha512(const Blob *key, const Blob *data) {
#if defined(__APPLE__)
    size_t key_size = 0;
    size_t data_size = 0;
    const uint8_t *key_bytes = ez_blob_data(key, &key_size);
    const uint8_t *data_bytes = ez_blob_data(data, &data_size);
    if ((!key_bytes && key_size > 0) || (!data_bytes && data_size > 0)) return (OptBlob){false, {0}};
    uint8_t *out = (uint8_t *)malloc(CC_SHA512_DIGEST_LENGTH);
    if (!out) return (OptBlob){false, {0}};
    CCHmac(kCCHmacAlgSHA512, key_bytes ? key_bytes : (const uint8_t *)"", key_size,
           data_bytes ? data_bytes : (const uint8_t *)"", data_size, out);
    return ez_blob_result(out, CC_SHA512_DIGEST_LENGTH);
#else
    (void)key;
    (void)data;
    return (OptBlob){false, {0}};
#endif
}
