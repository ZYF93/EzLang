// EzLang std/crypto 原生封装层
// 成熟平台加密库优先；不可用或强制 portable 时使用同步 SHA-2/HMAC 回退。

#include <stdbool.h>
#include <stdint.h>
#include <limits.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#ifndef EZ_CRYPTO_FORCE_PORTABLE
#define EZ_CRYPTO_FORCE_PORTABLE 0
#endif

#ifndef __has_include
#define __has_include(x) 0
#endif

#if !EZ_CRYPTO_FORCE_PORTABLE && defined(__APPLE__) && __has_include(<CommonCrypto/CommonCrypto.h>)
#define EZ_CRYPTO_HAS_COMMONCRYPTO 1
#include <CommonCrypto/CommonCrypto.h>
#else
#define EZ_CRYPTO_HAS_COMMONCRYPTO 0
#endif

#if !EZ_CRYPTO_FORCE_PORTABLE && defined(__linux__) && !defined(__ANDROID__) && __has_include(<dlfcn.h>)
#define EZ_CRYPTO_HAS_OPENSSL 1
#include <dlfcn.h>
#else
#define EZ_CRYPTO_HAS_OPENSSL 0
#endif

#if !EZ_CRYPTO_FORCE_PORTABLE && defined(_WIN32) && __has_include(<windows.h>) && __has_include(<bcrypt.h>)
#define EZ_CRYPTO_HAS_BCRYPT 1
#include <windows.h>
#include <bcrypt.h>
#ifndef NT_SUCCESS
#define NT_SUCCESS(status) (((NTSTATUS)(status)) >= 0)
#endif
#else
#define EZ_CRYPTO_HAS_BCRYPT 0
#endif

#define EZ_CRYPTO_HAS_PORTABLE 1

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

typedef struct { bool ok; Blob value; } OptBlob;

static OptBlob ez_none_blob(void) {
    return (OptBlob){false, {NULL, 0}};
}

static bool ez_blob_bytes(const Blob *blob, const uint8_t **bytes, size_t *size) {
    static const uint8_t empty[1] = {0};
    *bytes = empty;
    *size = 0;
    if (!blob || blob->size < 0 || (blob->size > 0 && !blob->data)) {
        return false;
    }
    if ((uint64_t)blob->size > SIZE_MAX) {
        return false;
    }
    *size = (size_t)blob->size;
    *bytes = blob->data ? blob->data : empty;
    return true;
}

static OptBlob ez_blob_result(uint8_t *data, size_t size) {
    if (!data && size > 0) return ez_none_blob();
    return (OptBlob){true, {data, (int64_t)size}};
}

#if EZ_CRYPTO_HAS_COMMONCRYPTO
typedef unsigned char *(*EzCCDigestFn)(const void *, CC_LONG, unsigned char *);

static OptBlob ez_commoncrypto_digest(const Blob *data, size_t digest_size, EzCCDigestFn digest_fn) {
    const uint8_t *bytes = NULL;
    size_t size = 0;
    if (!ez_blob_bytes(data, &bytes, &size) || size > UINT32_MAX) return ez_none_blob();
    uint8_t *out = (uint8_t *)malloc(digest_size);
    if (!out) return ez_none_blob();
    digest_fn(bytes, (CC_LONG)size, out);
    return ez_blob_result(out, digest_size);
}

static OptBlob ez_commoncrypto_hmac(const Blob *key, const Blob *data, CCHmacAlgorithm algorithm, size_t digest_size) {
    const uint8_t *key_bytes = NULL;
    const uint8_t *data_bytes = NULL;
    size_t key_size = 0;
    size_t data_size = 0;
    if (!ez_blob_bytes(key, &key_bytes, &key_size) || !ez_blob_bytes(data, &data_bytes, &data_size)) return ez_none_blob();
    uint8_t *out = (uint8_t *)malloc(digest_size);
    if (!out) return ez_none_blob();
    CCHmac(algorithm, key_bytes, key_size, data_bytes, data_size, out);
    return ez_blob_result(out, digest_size);
}
#endif

#if EZ_CRYPTO_HAS_OPENSSL
typedef struct evp_md_st EVP_MD;
typedef struct evp_md_ctx_st EVP_MD_CTX;

typedef const EVP_MD *(*EzOpenSslMdFn)(void);
typedef EVP_MD_CTX *(*EzOpenSslCtxNewFn)(void);
typedef void (*EzOpenSslCtxFreeFn)(EVP_MD_CTX *);
typedef int (*EzOpenSslDigestInitFn)(EVP_MD_CTX *, const EVP_MD *, void *);
typedef int (*EzOpenSslDigestUpdateFn)(EVP_MD_CTX *, const void *, size_t);
typedef int (*EzOpenSslDigestFinalFn)(EVP_MD_CTX *, unsigned char *, unsigned int *);
typedef unsigned char *(*EzOpenSslHmacFn)(const EVP_MD *, const void *, int, const unsigned char *, size_t, unsigned char *, unsigned int *);

typedef struct {
    void *handle;
    EzOpenSslMdFn sha256;
    EzOpenSslMdFn sha512;
    EzOpenSslCtxNewFn ctx_new;
    EzOpenSslCtxFreeFn ctx_free;
    EzOpenSslDigestInitFn digest_init;
    EzOpenSslDigestUpdateFn digest_update;
    EzOpenSslDigestFinalFn digest_final;
    EzOpenSslHmacFn hmac;
    bool loaded;
    bool available;
} EzOpenSslApi;

static EzOpenSslApi ez_openssl_api = {0};

static void *ez_dlsym_required(void *handle, const char *name, bool *ok) {
    void *symbol = dlsym(handle, name);
    if (!symbol) *ok = false;
    return symbol;
}

static bool ez_load_openssl(EzOpenSslApi *api) {
    if (api->loaded) return api->available;
    api->loaded = true;
    const char *candidates[] = {
        "libcrypto.so.3",
        "libcrypto.so.1.1",
        "libcrypto.so",
        NULL,
    };
    for (size_t i = 0; candidates[i] != NULL; ++i) {
#if defined(EZ_CRYPTO_TEST_NO_OPENSSL_DLOPEN)
        api->handle = NULL;
#else
        api->handle = dlopen(candidates[i], RTLD_LAZY | RTLD_LOCAL);
#endif
        if (api->handle) break;
    }
    if (!api->handle) return false;

    bool ok = true;
    api->sha256 = (EzOpenSslMdFn)ez_dlsym_required(api->handle, "EVP_sha256", &ok);
    api->sha512 = (EzOpenSslMdFn)ez_dlsym_required(api->handle, "EVP_sha512", &ok);
    api->ctx_new = (EzOpenSslCtxNewFn)ez_dlsym_required(api->handle, "EVP_MD_CTX_new", &ok);
    api->ctx_free = (EzOpenSslCtxFreeFn)ez_dlsym_required(api->handle, "EVP_MD_CTX_free", &ok);
    api->digest_init = (EzOpenSslDigestInitFn)ez_dlsym_required(api->handle, "EVP_DigestInit_ex", &ok);
    api->digest_update = (EzOpenSslDigestUpdateFn)ez_dlsym_required(api->handle, "EVP_DigestUpdate", &ok);
    api->digest_final = (EzOpenSslDigestFinalFn)ez_dlsym_required(api->handle, "EVP_DigestFinal_ex", &ok);
    api->hmac = (EzOpenSslHmacFn)ez_dlsym_required(api->handle, "HMAC", &ok);
    if (!ok) {
        dlclose(api->handle);
        memset(api, 0, sizeof(*api));
        api->loaded = true;
        return false;
    }
    api->available = true;
    return true;
}

static OptBlob ez_openssl_digest(const Blob *data, EzOpenSslMdFn algorithm, size_t digest_size) {
    const uint8_t *bytes = NULL;
    size_t size = 0;
    if (!ez_blob_bytes(data, &bytes, &size)) return ez_none_blob();
    if (!algorithm) return ez_none_blob();

    EzOpenSslApi *api = &ez_openssl_api;
    if (!ez_load_openssl(api)) return ez_none_blob();

    const EVP_MD *md = algorithm();
    if (!md) return ez_none_blob();

    EVP_MD_CTX *ctx = api->ctx_new();
    uint8_t *out = (uint8_t *)malloc(digest_size);
    if (!ctx || !out) {
        api->ctx_free(ctx);
        free(out);
        return ez_none_blob();
    }

    unsigned int out_size = 0;
    bool ok = api->digest_init(ctx, md, NULL) == 1 &&
              api->digest_update(ctx, bytes, size) == 1 &&
              api->digest_final(ctx, out, &out_size) == 1 &&
              out_size == (unsigned int)digest_size;
    api->ctx_free(ctx);
    if (!ok) {
        free(out);
        return ez_none_blob();
    }
    return ez_blob_result(out, out_size);
}

static OptBlob ez_openssl_hmac(const Blob *key, const Blob *data, EzOpenSslMdFn algorithm, size_t digest_size) {
    const uint8_t *key_bytes = NULL;
    const uint8_t *data_bytes = NULL;
    size_t key_size = 0;
    size_t data_size = 0;
    if (!ez_blob_bytes(key, &key_bytes, &key_size) || !ez_blob_bytes(data, &data_bytes, &data_size)) return ez_none_blob();
    if (key_size > INT_MAX) return ez_none_blob();
    if (!algorithm) return ez_none_blob();

    EzOpenSslApi *api = &ez_openssl_api;
    if (!ez_load_openssl(api)) return ez_none_blob();

    const EVP_MD *md = algorithm();
    if (!md) return ez_none_blob();

    uint8_t *out = (uint8_t *)malloc(digest_size);
    if (!out) return ez_none_blob();

    unsigned int out_size = 0;
    unsigned char *result = api->hmac(md, key_bytes, (int)key_size, data_bytes, data_size, out, &out_size);
    if (!result || out_size != (unsigned int)digest_size) {
        free(out);
        return ez_none_blob();
    }
    return ez_blob_result(out, out_size);
}
#endif

#if EZ_CRYPTO_HAS_BCRYPT
static bool ez_size_to_ulong(size_t size, ULONG *out) {
    if (size > ULONG_MAX) return false;
    *out = (ULONG)size;
    return true;
}

static OptBlob ez_bcrypt_hash(const Blob *key, const Blob *data, LPCWSTR algorithm, ULONG expected_size) {
    const uint8_t *data_bytes = NULL;
    const uint8_t *key_bytes = NULL;
    size_t data_size = 0;
    size_t key_size = 0;
    if (!ez_blob_bytes(data, &data_bytes, &data_size)) return ez_none_blob();
    bool use_hmac = key != NULL;
    if (use_hmac && !ez_blob_bytes(key, &key_bytes, &key_size)) return ez_none_blob();

    ULONG data_len = 0;
    ULONG key_len = 0;
    if (!ez_size_to_ulong(data_size, &data_len) || !ez_size_to_ulong(key_size, &key_len)) return ez_none_blob();

    BCRYPT_ALG_HANDLE alg = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    uint8_t *hash_object = NULL;
    uint8_t *out = NULL;
    DWORD object_len = 0;
    DWORD hash_len = 0;
    DWORD returned = 0;
    ULONG flags = use_hmac ? BCRYPT_ALG_HANDLE_HMAC_FLAG : 0;

    NTSTATUS status = BCryptOpenAlgorithmProvider(&alg, algorithm, NULL, flags);
    if (!NT_SUCCESS(status)) goto fail;
    status = BCryptGetProperty(alg, BCRYPT_OBJECT_LENGTH, (PUCHAR)&object_len, sizeof(object_len), &returned, 0);
    if (!NT_SUCCESS(status) || object_len == 0) goto fail;
    status = BCryptGetProperty(alg, BCRYPT_HASH_LENGTH, (PUCHAR)&hash_len, sizeof(hash_len), &returned, 0);
    if (!NT_SUCCESS(status) || hash_len != expected_size) goto fail;

    hash_object = (uint8_t *)malloc(object_len);
    out = (uint8_t *)malloc(hash_len);
    if (!hash_object || !out) goto fail;

    status = BCryptCreateHash(alg, &hash, hash_object, object_len, use_hmac ? (PUCHAR)key_bytes : NULL, use_hmac ? key_len : 0, 0);
    if (!NT_SUCCESS(status)) goto fail;
    status = BCryptHashData(hash, (PUCHAR)data_bytes, data_len, 0);
    if (!NT_SUCCESS(status)) goto fail;
    status = BCryptFinishHash(hash, out, hash_len, 0);
    if (!NT_SUCCESS(status)) goto fail;

    BCryptDestroyHash(hash);
    BCryptCloseAlgorithmProvider(alg, 0);
    free(hash_object);
    return ez_blob_result(out, hash_len);

fail:
    if (hash) BCryptDestroyHash(hash);
    if (alg) BCryptCloseAlgorithmProvider(alg, 0);
    free(hash_object);
    free(out);
    return ez_none_blob();
}
#endif

#include "crypto_portable.inc"

OptBlob cryptoSha256(const Blob *data) {
#if EZ_CRYPTO_HAS_COMMONCRYPTO
    {
        OptBlob result = ez_commoncrypto_digest(data, CC_SHA256_DIGEST_LENGTH, CC_SHA256);
        if (result.ok) return result;
    }
#endif
#if EZ_CRYPTO_HAS_OPENSSL
    {
        OptBlob result = ez_openssl_digest(data, ez_openssl_api.sha256 ? ez_openssl_api.sha256 : (ez_load_openssl(&ez_openssl_api) ? ez_openssl_api.sha256 : NULL), 32);
        if (result.ok) return result;
    }
#endif
#if EZ_CRYPTO_HAS_BCRYPT
    {
        OptBlob result = ez_bcrypt_hash(NULL, data, BCRYPT_SHA256_ALGORITHM, 32);
        if (result.ok) return result;
    }
#endif
    return ez_portable_digest_alloc(data, 32, ez_sha256_digest_bytes);
}

OptBlob cryptoSha512(const Blob *data) {
#if EZ_CRYPTO_HAS_COMMONCRYPTO
    {
        OptBlob result = ez_commoncrypto_digest(data, CC_SHA512_DIGEST_LENGTH, CC_SHA512);
        if (result.ok) return result;
    }
#endif
#if EZ_CRYPTO_HAS_OPENSSL
    {
        OptBlob result = ez_openssl_digest(data, ez_openssl_api.sha512 ? ez_openssl_api.sha512 : (ez_load_openssl(&ez_openssl_api) ? ez_openssl_api.sha512 : NULL), 64);
        if (result.ok) return result;
    }
#endif
#if EZ_CRYPTO_HAS_BCRYPT
    {
        OptBlob result = ez_bcrypt_hash(NULL, data, BCRYPT_SHA512_ALGORITHM, 64);
        if (result.ok) return result;
    }
#endif
    return ez_portable_digest_alloc(data, 64, ez_sha512_digest_bytes);
}

OptBlob cryptoHmacSha256(const Blob *key, const Blob *data) {
#if EZ_CRYPTO_HAS_COMMONCRYPTO
    {
        OptBlob result = ez_commoncrypto_hmac(key, data, kCCHmacAlgSHA256, CC_SHA256_DIGEST_LENGTH);
        if (result.ok) return result;
    }
#endif
#if EZ_CRYPTO_HAS_OPENSSL
    {
        OptBlob result = ez_openssl_hmac(key, data, ez_openssl_api.sha256 ? ez_openssl_api.sha256 : (ez_load_openssl(&ez_openssl_api) ? ez_openssl_api.sha256 : NULL), 32);
        if (result.ok) return result;
    }
#endif
#if EZ_CRYPTO_HAS_BCRYPT
    {
        OptBlob result = ez_bcrypt_hash(key, data, BCRYPT_SHA256_ALGORITHM, 32);
        if (result.ok) return result;
    }
#endif
    return ez_hmac_sha256_alloc(key, data);
}

OptBlob cryptoHmacSha512(const Blob *key, const Blob *data) {
#if EZ_CRYPTO_HAS_COMMONCRYPTO
    {
        OptBlob result = ez_commoncrypto_hmac(key, data, kCCHmacAlgSHA512, CC_SHA512_DIGEST_LENGTH);
        if (result.ok) return result;
    }
#endif
#if EZ_CRYPTO_HAS_OPENSSL
    {
        OptBlob result = ez_openssl_hmac(key, data, ez_openssl_api.sha512 ? ez_openssl_api.sha512 : (ez_load_openssl(&ez_openssl_api) ? ez_openssl_api.sha512 : NULL), 64);
        if (result.ok) return result;
    }
#endif
#if EZ_CRYPTO_HAS_BCRYPT
    {
        OptBlob result = ez_bcrypt_hash(key, data, BCRYPT_SHA512_ALGORITHM, 64);
        if (result.ok) return result;
    }
#endif
    return ez_hmac_sha512_alloc(key, data);
}
