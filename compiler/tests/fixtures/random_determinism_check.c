#include <stdint.h>
#include <stdio.h>

#include "../../../packages/std/native/random.c"

int main(void) {
    RandomSource source = {0xA8D395BE4B19CCE8ULL};
    int64_t ranged = randomRangeI64(&source, 0, 1);
    uint64_t next = randomNextU64(&source);
    printf("%lld\n", (long long)ranged);
    printf("%llu\n", (unsigned long long)next);
    return 0;
}
