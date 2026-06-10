// std/crypto 的同步 SHA-2/HMAC 回退实现，由 crypto.c 按需包含。

static uint32_t ez_rotr32(uint32_t value, unsigned int bits) {
    return (value >> bits) | (value << (32U - bits));
}

static uint64_t ez_rotr64(uint64_t value, unsigned int bits) {
    return (value >> bits) | (value << (64U - bits));
}

static uint32_t ez_read_be32(const uint8_t *bytes) {
    return ((uint32_t)bytes[0] << 24) |
           ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) |
           (uint32_t)bytes[3];
}

static uint64_t ez_read_be64(const uint8_t *bytes) {
    return ((uint64_t)bytes[0] << 56) |
           ((uint64_t)bytes[1] << 48) |
           ((uint64_t)bytes[2] << 40) |
           ((uint64_t)bytes[3] << 32) |
           ((uint64_t)bytes[4] << 24) |
           ((uint64_t)bytes[5] << 16) |
           ((uint64_t)bytes[6] << 8) |
           (uint64_t)bytes[7];
}

static void ez_write_be32(uint8_t *out, uint32_t value) {
    out[0] = (uint8_t)(value >> 24);
    out[1] = (uint8_t)(value >> 16);
    out[2] = (uint8_t)(value >> 8);
    out[3] = (uint8_t)value;
}

static void ez_write_be64(uint8_t *out, uint64_t value) {
    out[0] = (uint8_t)(value >> 56);
    out[1] = (uint8_t)(value >> 48);
    out[2] = (uint8_t)(value >> 40);
    out[3] = (uint8_t)(value >> 32);
    out[4] = (uint8_t)(value >> 24);
    out[5] = (uint8_t)(value >> 16);
    out[6] = (uint8_t)(value >> 8);
    out[7] = (uint8_t)value;
}

typedef struct {
    uint32_t state[8];
    uint64_t bit_len;
    uint8_t buffer[64];
    size_t buffer_len;
} EzSha256Ctx;

static const uint32_t EZ_SHA256_K[64] = {
    0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
    0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
    0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
    0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
    0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
    0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
    0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
    0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
    0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
    0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
    0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
    0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
    0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
    0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
    0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
    0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U,
};

static void ez_sha256_transform(EzSha256Ctx *ctx, const uint8_t block[64]) {
    uint32_t words[64];
    for (size_t i = 0; i < 16; ++i) words[i] = ez_read_be32(block + i * 4);
    for (size_t i = 16; i < 64; ++i) {
        uint32_t s0 = ez_rotr32(words[i - 15], 7) ^ ez_rotr32(words[i - 15], 18) ^ (words[i - 15] >> 3);
        uint32_t s1 = ez_rotr32(words[i - 2], 17) ^ ez_rotr32(words[i - 2], 19) ^ (words[i - 2] >> 10);
        words[i] = words[i - 16] + s0 + words[i - 7] + s1;
    }

    uint32_t a = ctx->state[0], b = ctx->state[1], c = ctx->state[2], d = ctx->state[3];
    uint32_t e = ctx->state[4], f = ctx->state[5], g = ctx->state[6], h = ctx->state[7];
    for (size_t i = 0; i < 64; ++i) {
        uint32_t s1 = ez_rotr32(e, 6) ^ ez_rotr32(e, 11) ^ ez_rotr32(e, 25);
        uint32_t ch = (e & f) ^ (~e & g);
        uint32_t temp1 = h + s1 + ch + EZ_SHA256_K[i] + words[i];
        uint32_t s0 = ez_rotr32(a, 2) ^ ez_rotr32(a, 13) ^ ez_rotr32(a, 22);
        uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        uint32_t temp2 = s0 + maj;
        h = g;
        g = f;
        f = e;
        e = d + temp1;
        d = c;
        c = b;
        b = a;
        a = temp1 + temp2;
    }
    ctx->state[0] += a;
    ctx->state[1] += b;
    ctx->state[2] += c;
    ctx->state[3] += d;
    ctx->state[4] += e;
    ctx->state[5] += f;
    ctx->state[6] += g;
    ctx->state[7] += h;
}

static void ez_sha256_init(EzSha256Ctx *ctx) {
    ctx->state[0] = 0x6a09e667U;
    ctx->state[1] = 0xbb67ae85U;
    ctx->state[2] = 0x3c6ef372U;
    ctx->state[3] = 0xa54ff53aU;
    ctx->state[4] = 0x510e527fU;
    ctx->state[5] = 0x9b05688cU;
    ctx->state[6] = 0x1f83d9abU;
    ctx->state[7] = 0x5be0cd19U;
    ctx->bit_len = 0;
    ctx->buffer_len = 0;
}

static void ez_sha256_update(EzSha256Ctx *ctx, const uint8_t *bytes, size_t size) {
    ctx->bit_len += (uint64_t)size << 3;
    while (size > 0) {
        size_t room = sizeof(ctx->buffer) - ctx->buffer_len;
        size_t take = size < room ? size : room;
        memcpy(ctx->buffer + ctx->buffer_len, bytes, take);
        ctx->buffer_len += take;
        bytes += take;
        size -= take;
        if (ctx->buffer_len == sizeof(ctx->buffer)) {
            ez_sha256_transform(ctx, ctx->buffer);
            ctx->buffer_len = 0;
        }
    }
}

static void ez_sha256_final(EzSha256Ctx *ctx, uint8_t out[32]) {
    ctx->buffer[ctx->buffer_len++] = 0x80;
    if (ctx->buffer_len > 56) {
        memset(ctx->buffer + ctx->buffer_len, 0, sizeof(ctx->buffer) - ctx->buffer_len);
        ez_sha256_transform(ctx, ctx->buffer);
        ctx->buffer_len = 0;
    }
    memset(ctx->buffer + ctx->buffer_len, 0, 56 - ctx->buffer_len);
    ez_write_be64(ctx->buffer + 56, ctx->bit_len);
    ez_sha256_transform(ctx, ctx->buffer);
    for (size_t i = 0; i < 8; ++i) ez_write_be32(out + i * 4, ctx->state[i]);
}

static void ez_sha256_digest_bytes(const uint8_t *bytes, size_t size, uint8_t out[32]) {
    EzSha256Ctx ctx;
    ez_sha256_init(&ctx);
    ez_sha256_update(&ctx, bytes, size);
    ez_sha256_final(&ctx, out);
}

typedef struct {
    uint64_t state[8];
    uint64_t bit_len_hi;
    uint64_t bit_len_lo;
    uint8_t buffer[128];
    size_t buffer_len;
} EzSha512Ctx;

static const uint64_t EZ_SHA512_K[80] = {
    UINT64_C(0x428a2f98d728ae22), UINT64_C(0x7137449123ef65cd),
    UINT64_C(0xb5c0fbcfec4d3b2f), UINT64_C(0xe9b5dba58189dbbc),
    UINT64_C(0x3956c25bf348b538), UINT64_C(0x59f111f1b605d019),
    UINT64_C(0x923f82a4af194f9b), UINT64_C(0xab1c5ed5da6d8118),
    UINT64_C(0xd807aa98a3030242), UINT64_C(0x12835b0145706fbe),
    UINT64_C(0x243185be4ee4b28c), UINT64_C(0x550c7dc3d5ffb4e2),
    UINT64_C(0x72be5d74f27b896f), UINT64_C(0x80deb1fe3b1696b1),
    UINT64_C(0x9bdc06a725c71235), UINT64_C(0xc19bf174cf692694),
    UINT64_C(0xe49b69c19ef14ad2), UINT64_C(0xefbe4786384f25e3),
    UINT64_C(0x0fc19dc68b8cd5b5), UINT64_C(0x240ca1cc77ac9c65),
    UINT64_C(0x2de92c6f592b0275), UINT64_C(0x4a7484aa6ea6e483),
    UINT64_C(0x5cb0a9dcbd41fbd4), UINT64_C(0x76f988da831153b5),
    UINT64_C(0x983e5152ee66dfab), UINT64_C(0xa831c66d2db43210),
    UINT64_C(0xb00327c898fb213f), UINT64_C(0xbf597fc7beef0ee4),
    UINT64_C(0xc6e00bf33da88fc2), UINT64_C(0xd5a79147930aa725),
    UINT64_C(0x06ca6351e003826f), UINT64_C(0x142929670a0e6e70),
    UINT64_C(0x27b70a8546d22ffc), UINT64_C(0x2e1b21385c26c926),
    UINT64_C(0x4d2c6dfc5ac42aed), UINT64_C(0x53380d139d95b3df),
    UINT64_C(0x650a73548baf63de), UINT64_C(0x766a0abb3c77b2a8),
    UINT64_C(0x81c2c92e47edaee6), UINT64_C(0x92722c851482353b),
    UINT64_C(0xa2bfe8a14cf10364), UINT64_C(0xa81a664bbc423001),
    UINT64_C(0xc24b8b70d0f89791), UINT64_C(0xc76c51a30654be30),
    UINT64_C(0xd192e819d6ef5218), UINT64_C(0xd69906245565a910),
    UINT64_C(0xf40e35855771202a), UINT64_C(0x106aa07032bbd1b8),
    UINT64_C(0x19a4c116b8d2d0c8), UINT64_C(0x1e376c085141ab53),
    UINT64_C(0x2748774cdf8eeb99), UINT64_C(0x34b0bcb5e19b48a8),
    UINT64_C(0x391c0cb3c5c95a63), UINT64_C(0x4ed8aa4ae3418acb),
    UINT64_C(0x5b9cca4f7763e373), UINT64_C(0x682e6ff3d6b2b8a3),
    UINT64_C(0x748f82ee5defb2fc), UINT64_C(0x78a5636f43172f60),
    UINT64_C(0x84c87814a1f0ab72), UINT64_C(0x8cc702081a6439ec),
    UINT64_C(0x90befffa23631e28), UINT64_C(0xa4506cebde82bde9),
    UINT64_C(0xbef9a3f7b2c67915), UINT64_C(0xc67178f2e372532b),
    UINT64_C(0xca273eceea26619c), UINT64_C(0xd186b8c721c0c207),
    UINT64_C(0xeada7dd6cde0eb1e), UINT64_C(0xf57d4f7fee6ed178),
    UINT64_C(0x06f067aa72176fba), UINT64_C(0x0a637dc5a2c898a6),
    UINT64_C(0x113f9804bef90dae), UINT64_C(0x1b710b35131c471b),
    UINT64_C(0x28db77f523047d84), UINT64_C(0x32caab7b40c72493),
    UINT64_C(0x3c9ebe0a15c9bebc), UINT64_C(0x431d67c49c100d4c),
    UINT64_C(0x4cc5d4becb3e42b6), UINT64_C(0x597f299cfc657e2a),
    UINT64_C(0x5fcb6fab3ad6faec), UINT64_C(0x6c44198c4a475817),
};

static void ez_sha512_transform(EzSha512Ctx *ctx, const uint8_t block[128]) {
    uint64_t words[80];
    for (size_t i = 0; i < 16; ++i) words[i] = ez_read_be64(block + i * 8);
    for (size_t i = 16; i < 80; ++i) {
        uint64_t s0 = ez_rotr64(words[i - 15], 1) ^ ez_rotr64(words[i - 15], 8) ^ (words[i - 15] >> 7);
        uint64_t s1 = ez_rotr64(words[i - 2], 19) ^ ez_rotr64(words[i - 2], 61) ^ (words[i - 2] >> 6);
        words[i] = words[i - 16] + s0 + words[i - 7] + s1;
    }

    uint64_t a = ctx->state[0], b = ctx->state[1], c = ctx->state[2], d = ctx->state[3];
    uint64_t e = ctx->state[4], f = ctx->state[5], g = ctx->state[6], h = ctx->state[7];
    for (size_t i = 0; i < 80; ++i) {
        uint64_t s1 = ez_rotr64(e, 14) ^ ez_rotr64(e, 18) ^ ez_rotr64(e, 41);
        uint64_t ch = (e & f) ^ (~e & g);
        uint64_t temp1 = h + s1 + ch + EZ_SHA512_K[i] + words[i];
        uint64_t s0 = ez_rotr64(a, 28) ^ ez_rotr64(a, 34) ^ ez_rotr64(a, 39);
        uint64_t maj = (a & b) ^ (a & c) ^ (b & c);
        uint64_t temp2 = s0 + maj;
        h = g;
        g = f;
        f = e;
        e = d + temp1;
        d = c;
        c = b;
        b = a;
        a = temp1 + temp2;
    }
    ctx->state[0] += a;
    ctx->state[1] += b;
    ctx->state[2] += c;
    ctx->state[3] += d;
    ctx->state[4] += e;
    ctx->state[5] += f;
    ctx->state[6] += g;
    ctx->state[7] += h;
}

static void ez_sha512_init(EzSha512Ctx *ctx) {
    ctx->state[0] = UINT64_C(0x6a09e667f3bcc908);
    ctx->state[1] = UINT64_C(0xbb67ae8584caa73b);
    ctx->state[2] = UINT64_C(0x3c6ef372fe94f82b);
    ctx->state[3] = UINT64_C(0xa54ff53a5f1d36f1);
    ctx->state[4] = UINT64_C(0x510e527fade682d1);
    ctx->state[5] = UINT64_C(0x9b05688c2b3e6c1f);
    ctx->state[6] = UINT64_C(0x1f83d9abfb41bd6b);
    ctx->state[7] = UINT64_C(0x5be0cd19137e2179);
    ctx->bit_len_hi = 0;
    ctx->bit_len_lo = 0;
    ctx->buffer_len = 0;
}

static void ez_sha512_add_bits(EzSha512Ctx *ctx, size_t size) {
    uint64_t add_lo = (uint64_t)size << 3;
    uint64_t add_hi = (uint64_t)size >> 61;
    ctx->bit_len_lo += add_lo;
    if (ctx->bit_len_lo < add_lo) ctx->bit_len_hi += 1;
    ctx->bit_len_hi += add_hi;
}

static void ez_sha512_update(EzSha512Ctx *ctx, const uint8_t *bytes, size_t size) {
    ez_sha512_add_bits(ctx, size);
    while (size > 0) {
        size_t room = sizeof(ctx->buffer) - ctx->buffer_len;
        size_t take = size < room ? size : room;
        memcpy(ctx->buffer + ctx->buffer_len, bytes, take);
        ctx->buffer_len += take;
        bytes += take;
        size -= take;
        if (ctx->buffer_len == sizeof(ctx->buffer)) {
            ez_sha512_transform(ctx, ctx->buffer);
            ctx->buffer_len = 0;
        }
    }
}

static void ez_sha512_final(EzSha512Ctx *ctx, uint8_t out[64]) {
    ctx->buffer[ctx->buffer_len++] = 0x80;
    if (ctx->buffer_len > 112) {
        memset(ctx->buffer + ctx->buffer_len, 0, sizeof(ctx->buffer) - ctx->buffer_len);
        ez_sha512_transform(ctx, ctx->buffer);
        ctx->buffer_len = 0;
    }
    memset(ctx->buffer + ctx->buffer_len, 0, 112 - ctx->buffer_len);
    ez_write_be64(ctx->buffer + 112, ctx->bit_len_hi);
    ez_write_be64(ctx->buffer + 120, ctx->bit_len_lo);
    ez_sha512_transform(ctx, ctx->buffer);
    for (size_t i = 0; i < 8; ++i) ez_write_be64(out + i * 8, ctx->state[i]);
}

static void ez_sha512_digest_bytes(const uint8_t *bytes, size_t size, uint8_t out[64]) {
    EzSha512Ctx ctx;
    ez_sha512_init(&ctx);
    ez_sha512_update(&ctx, bytes, size);
    ez_sha512_final(&ctx, out);
}

typedef void (*EzPortableDigestFn)(const uint8_t *, size_t, uint8_t *);

static OptBlob ez_portable_digest_alloc(const Blob *data, size_t digest_size, EzPortableDigestFn digest_fn) {
    const uint8_t *bytes = NULL;
    size_t size = 0;
    if (!ez_blob_bytes(data, &bytes, &size)) return ez_none_blob();
    uint8_t *out = (uint8_t *)malloc(digest_size);
    if (!out) return ez_none_blob();
    digest_fn(bytes, size, out);
    return ez_blob_result(out, digest_size);
}

static OptBlob ez_hmac_alloc(const Blob *key, const Blob *data, size_t block_size, size_t digest_size, EzPortableDigestFn digest_fn) {
    const uint8_t *key_bytes = NULL;
    const uint8_t *data_bytes = NULL;
    size_t key_size = 0;
    size_t data_size = 0;
    if (!ez_blob_bytes(key, &key_bytes, &key_size) || !ez_blob_bytes(data, &data_bytes, &data_size)) return ez_none_blob();

    uint8_t normalized_key[128] = {0};
    uint8_t inner_pad[128];
    uint8_t outer_pad[128];
    uint8_t key_digest[64];
    if (block_size > sizeof(normalized_key) || digest_size > sizeof(key_digest)) return ez_none_blob();
    if (key_size > block_size) {
        digest_fn(key_bytes, key_size, key_digest);
        memcpy(normalized_key, key_digest, digest_size);
    } else if (key_size > 0) {
        memcpy(normalized_key, key_bytes, key_size);
    }
    for (size_t i = 0; i < block_size; ++i) {
        inner_pad[i] = normalized_key[i] ^ 0x36U;
        outer_pad[i] = normalized_key[i] ^ 0x5cU;
    }

    uint8_t *out = (uint8_t *)malloc(digest_size);
    if (!out) return ez_none_blob();
    if (digest_size == 32) {
        EzSha256Ctx ctx;
        uint8_t inner_digest[32];
        ez_sha256_init(&ctx);
        ez_sha256_update(&ctx, inner_pad, block_size);
        ez_sha256_update(&ctx, data_bytes, data_size);
        ez_sha256_final(&ctx, inner_digest);
        ez_sha256_init(&ctx);
        ez_sha256_update(&ctx, outer_pad, block_size);
        ez_sha256_update(&ctx, inner_digest, sizeof(inner_digest));
        ez_sha256_final(&ctx, out);
    } else if (digest_size == 64) {
        EzSha512Ctx ctx;
        uint8_t inner_digest[64];
        ez_sha512_init(&ctx);
        ez_sha512_update(&ctx, inner_pad, block_size);
        ez_sha512_update(&ctx, data_bytes, data_size);
        ez_sha512_final(&ctx, inner_digest);
        ez_sha512_init(&ctx);
        ez_sha512_update(&ctx, outer_pad, block_size);
        ez_sha512_update(&ctx, inner_digest, sizeof(inner_digest));
        ez_sha512_final(&ctx, out);
    } else {
        free(out);
        return ez_none_blob();
    }
    return ez_blob_result(out, digest_size);
}

static OptBlob ez_hmac_sha256_alloc(const Blob *key, const Blob *data) {
    return ez_hmac_alloc(key, data, 64, 32, ez_sha256_digest_bytes);
}

static OptBlob ez_hmac_sha512_alloc(const Blob *key, const Blob *data) {
    return ez_hmac_alloc(key, data, 128, 64, ez_sha512_digest_bytes);
}
