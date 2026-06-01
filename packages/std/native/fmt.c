// EzLang std/fmt 原生封装层
// TODO: 这里先提供标准库 ABI 占位实现，后续接入运行时分配器和完整编码库。

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

const char *toString(void *value) {
    (void)value;
    return "";
}

int32_t parseInt(const char *s) {
    return (int32_t)strtol(s, NULL, 10);
}

int64_t parseI64(const char *s) {
    return strtoll(s, NULL, 10);
}

double parseF64(const char *s) {
    return strtod(s, NULL);
}

const char *format(const char *template, const char **args) {
    (void)args;
    return template;
}

const char *b64Encode(Blob data) {
    (void)data;
    return "";
}

Blob *b64Decode(const char *s) {
    (void)s;
    return NULL;
}

const char *jsonStringify(void *data) {
    (void)data;
    return "null";
}

void *jsonParse(const char *s) {
    (void)s;
    return NULL;
}

Blob msgpackEncode(void *data) {
    (void)data;
    return (Blob){0};
}

void *msgpackDecode(Blob data) {
    (void)data;
    return NULL;
}

const char *urlEncode(const char *s) {
    return s;
}

const char *urlDecode(const char *s) {
    return s;
}
