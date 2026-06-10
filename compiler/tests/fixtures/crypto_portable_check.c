#define EZ_CRYPTO_FORCE_PORTABLE 1
#include "../../../packages/std/native/crypto.c"

#include <stdio.h>

static void print_hex(const Blob *blob) {
    for (int64_t i = 0; i < blob->size; ++i) {
        printf("%02x", blob->data[i]);
    }
    printf("\n");
}

int main(void) {
    Blob data = {(uint8_t *)"hello", 5};
    Blob key = {(uint8_t *)"key", 3};
    OptBlob sha256 = cryptoSha256(&data);
    OptBlob sha512 = cryptoSha512(&data);
    OptBlob h256 = cryptoHmacSha256(&key, &data);
    OptBlob h512 = cryptoHmacSha512(&key, &data);
    if (!sha256.ok || !sha512.ok || !h256.ok || !h512.ok) return 1;
    print_hex(&sha256.value);
    print_hex(&sha512.value);
    print_hex(&h256.value);
    print_hex(&h512.value);
    return 0;
}
