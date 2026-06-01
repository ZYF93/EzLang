// EzLang std/io 原生封装层
// 这些函数实现 EzLang 标准库 ABI，再在内部调用 C 标准库或平台 API。

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void print(const char *msg) {
    fputs(msg ? msg : "", stdout);
}

void println(const char *msg) {
    fputs(msg ? msg : "", stdout);
    fputc('\n', stdout);
}

void error(const char *msg) {
    fputs(msg ? msg : "", stderr);
}

const char *readLine(void) {
    static char buffer[4096];
    if (fgets(buffer, sizeof(buffer), stdin) == NULL) {
        return NULL;
    }
    size_t len = strlen(buffer);
    if (len > 0 && buffer[len - 1] == '\n') {
        buffer[len - 1] = '\0';
    }
    return buffer;
}
