// EzLang std/fs 原生封装层
// 这里实现跨桌面、Android、iOS 的最小文件系统适配。

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <direct.h>
#define EZ_PATH_SEP '\\'
#else
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>
#define EZ_PATH_SEP '/'
#endif

typedef struct {
    uint8_t *data;
    int64_t size;
} Blob;

typedef struct {
    int64_t size;
    bool isDir;
    int64_t modified;
    int64_t created;
} FileStat;

static const char *ez_fs_sandbox_root(void) {
#if defined(__ANDROID__)
    const char *root = getenv("EZLANG_ANDROID_DATA_DIR");
    return root && root[0] ? root : "/data/local/tmp/ezlang";
#elif defined(__APPLE__) && defined(TARGET_OS_IPHONE)
    const char *root = getenv("EZLANG_IOS_DOCUMENTS_DIR");
    return root && root[0] ? root : "/Documents";
#else
    return "";
#endif
}

static bool ez_fs_is_absolute(const char *path) {
    if (!path || !path[0]) return false;
#if defined(_WIN32)
    return (strlen(path) > 2 && path[1] == ':') || path[0] == '\\' || path[0] == '/';
#else
    return path[0] == '/';
#endif
}

static char *ez_fs_path(const char *path) {
    if (!path) return NULL;
    if (ez_fs_is_absolute(path)) return strdup(path);
    const char *root = ez_fs_sandbox_root();
    if (!root || !root[0]) return strdup(path);
    size_t root_len = strlen(root);
    size_t path_len = strlen(path);
    bool need_sep = root_len > 0 && root[root_len - 1] != '/' && root[root_len - 1] != '\\';
    char *result = (char *)malloc(root_len + path_len + (need_sep ? 2 : 1));
    if (!result) return NULL;
    memcpy(result, root, root_len);
    if (need_sep) result[root_len++] = EZ_PATH_SEP;
    memcpy(result + root_len, path, path_len + 1);
    return result;
}

static bool ez_fs_mkdir_one(const char *path) {
#if defined(_WIN32)
    return _mkdir(path) == 0;
#else
    return mkdir(path, 0777) == 0;
#endif
}

static void ez_fs_ensure_parent(const char *path) {
    if (!path) return;
    char *copy = strdup(path);
    if (!copy) return;
    for (char *p = copy + 1; *p; ++p) {
        if (*p == '/' || *p == '\\') {
            char saved = *p;
            *p = '\0';
            ez_fs_mkdir_one(copy);
            *p = saved;
        }
    }
    free(copy);
}

Blob readFile(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return (Blob){0};
    FILE *file = fopen(real_path, "rb");
    free(real_path);
    if (!file) return (Blob){0};
    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        return (Blob){0};
    }
    long size = ftell(file);
    if (size < 0) {
        fclose(file);
        return (Blob){0};
    }
    rewind(file);
    uint8_t *data = (uint8_t *)malloc((size_t)size);
    if (size > 0 && !data) {
        fclose(file);
        return (Blob){0};
    }
    size_t read = fread(data, 1, (size_t)size, file);
    fclose(file);
    if (read != (size_t)size) {
        free(data);
        return (Blob){0};
    }
    return (Blob){data, (int64_t)size};
}

static bool ez_fs_write(const char *path, Blob content, const char *mode) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return false;
    ez_fs_ensure_parent(real_path);
    FILE *file = fopen(real_path, mode);
    free(real_path);
    if (!file) return false;
    size_t written = fwrite(content.data, 1, (size_t)content.size, file);
    fclose(file);
    return written == (size_t)content.size;
}

bool writeFile(const char *path, Blob content) {
    return ez_fs_write(path, content, "wb");
}

bool appendFile(const char *path, Blob content) {
    return ez_fs_write(path, content, "ab");
}

bool removeFile(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return false;
    bool ok = remove(real_path) == 0;
    free(real_path);
    return ok;
}

bool mkdir(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return false;
    ez_fs_ensure_parent(real_path);
    bool ok = ez_fs_mkdir_one(real_path);
    free(real_path);
    return ok;
}

bool removeDir(const char *path, bool recursive) {
    (void)recursive;
    char *real_path = ez_fs_path(path);
    if (!real_path) return false;
#if defined(_WIN32)
    bool ok = _rmdir(real_path) == 0;
#else
    bool ok = rmdir(real_path) == 0;
#endif
    free(real_path);
    return ok;
}

const char **listDir(const char *path) {
    (void)path;
    return NULL;
}

bool exists(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return false;
#if defined(_WIN32)
    FILE *file = fopen(real_path, "rb");
    bool ok = file != NULL;
    if (file) fclose(file);
#else
    bool ok = access(real_path, F_OK) == 0;
#endif
    free(real_path);
    return ok;
}

bool isDir(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return false;
#if defined(_WIN32)
    bool ok = false;
#else
    struct stat st;
    bool ok = stat(real_path, &st) == 0 && S_ISDIR(st.st_mode);
#endif
    free(real_path);
    return ok;
}

FileStat *stat(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return NULL;
#if defined(_WIN32)
    free(real_path);
    return NULL;
#else
    struct stat st;
    if (stat(real_path, &st) != 0) {
        free(real_path);
        return NULL;
    }
    free(real_path);
    FileStat *result = (FileStat *)malloc(sizeof(FileStat));
    if (!result) return NULL;
    result->size = (int64_t)st.st_size;
    result->isDir = S_ISDIR(st.st_mode);
    result->modified = (int64_t)st.st_mtime;
#if defined(__APPLE__)
    result->created = (int64_t)st.st_birthtime;
#else
    result->created = (int64_t)st.st_ctime;
#endif
    return result;
#endif
}

const char *absPath(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return NULL;
#if defined(_WIN32)
    return real_path;
#else
    char *resolved = realpath(real_path, NULL);
    if (resolved) {
        free(real_path);
        return resolved;
    }
    return real_path;
#endif
}
