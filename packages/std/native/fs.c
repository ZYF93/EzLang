// EzLang std/fs 原生封装层
// 这里实现跨桌面、Android、iOS 的最小文件系统适配。

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#if defined(__APPLE__)
#include <TargetConditionals.h>
#endif

#if defined(_WIN32)
#include <direct.h>
#include <io.h>
#include <sys/stat.h>
#include <windows.h>
#define EZ_PATH_SEP '\\'
#else
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#define EZ_PATH_SEP '/'
#endif

#if defined(_WIN32)
#define EZ_ABI_NAME(name)
#elif defined(__APPLE__)
#define EZ_ABI_NAME(name) __asm__("_" #name)
#else
#define EZ_ABI_NAME(name) __asm__(#name)
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

typedef struct {
    char ***pages;
    int64_t length;
    int64_t capacity;
    int64_t page_count;
} StrList;

typedef struct {
    bool ok;
    FileStat value;
} OptFileStat;

static char *ez_fs_copy_str(const char *text) {
    if (!text) return NULL;
    size_t len = strlen(text) + 1;
    char *copy = (char *)malloc(len);
    if (!copy) return NULL;
    memcpy(copy, text, len);
    return copy;
}

static const char *ez_fs_sandbox_root(void) {
#if defined(__ANDROID__)
    const char *root = getenv("EZLANG_ANDROID_DATA_DIR");
    return root && root[0] ? root : "/data/local/tmp/ezlang";
#elif defined(__APPLE__) && TARGET_OS_IPHONE
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

static bool ez_fs_valid_path(const char *path) {
    return path && path[0] != '\0';
}

static char *ez_fs_path(const char *path) {
    if (!ez_fs_valid_path(path)) return NULL;
    if (ez_fs_is_absolute(path)) return ez_fs_copy_str(path);
    const char *root = ez_fs_sandbox_root();
    if (!root || !root[0]) return ez_fs_copy_str(path);
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
    return mkdirat(AT_FDCWD, path, 0777) == 0;
#endif
}

static bool ez_fs_remove_tree(const char *path) {
#if defined(_WIN32)
    size_t path_len = strlen(path);
    size_t pattern_len = path_len + 3;
    char *pattern = (char *)malloc(pattern_len);
    if (!pattern) return false;
    snprintf(pattern, pattern_len, "%s\\*", path);

    WIN32_FIND_DATAA data;
    HANDLE handle = FindFirstFileA(pattern, &data);
    free(pattern);
    if (handle != INVALID_HANDLE_VALUE) {
        do {
            if (strcmp(data.cFileName, ".") == 0 || strcmp(data.cFileName, "..") == 0) continue;
            size_t child_len = path_len + strlen(data.cFileName) + 2;
            char *child = (char *)malloc(child_len);
            if (!child) {
                FindClose(handle);
                return false;
            }
            snprintf(child, child_len, "%s\\%s", path, data.cFileName);
            bool ok;
            if ((data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) {
                ok = ez_fs_remove_tree(child);
            } else {
                SetFileAttributesA(child, FILE_ATTRIBUTE_NORMAL);
                ok = DeleteFileA(child) != 0;
            }
            free(child);
            if (!ok) {
                FindClose(handle);
                return false;
            }
        } while (FindNextFileA(handle, &data) != 0);
        FindClose(handle);
    }
    SetFileAttributesA(path, FILE_ATTRIBUTE_NORMAL);
    return _rmdir(path) == 0;
#else
    DIR *dir = opendir(path);
    if (!dir) return rmdir(path) == 0;
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;
        size_t len = strlen(path) + strlen(entry->d_name) + 2;
        char *child = (char *)malloc(len);
        if (!child) {
            closedir(dir);
            return false;
        }
        snprintf(child, len, "%s/%s", path, entry->d_name);
        struct stat st;
        bool ok = lstat(child, &st) == 0;
        if (ok && S_ISDIR(st.st_mode)) {
            ok = ez_fs_remove_tree(child);
        } else if (ok) {
            ok = remove(child) == 0;
        }
        free(child);
        if (!ok) {
            closedir(dir);
            return false;
        }
    }
    closedir(dir);
    return rmdir(path) == 0;
#endif
}

static StrList ez_fs_list_dir(const char *path) {
#if defined(_WIN32)
    size_t path_len = strlen(path);
    size_t pattern_len = path_len + 3;
    char *pattern = (char *)malloc(pattern_len);
    if (!pattern) return (StrList){0};
    snprintf(pattern, pattern_len, "%s\\*", path);

    WIN32_FIND_DATAA data;
    HANDLE handle = FindFirstFileA(pattern, &data);
    free(pattern);
    if (handle == INVALID_HANDLE_VALUE) return (StrList){0};

    size_t count = 0;
    size_t cap = 8;
    char **flat = (char **)calloc(cap, sizeof(char *));
    if (!flat) {
        FindClose(handle);
        return (StrList){0};
    }
    do {
        if (strcmp(data.cFileName, ".") == 0 || strcmp(data.cFileName, "..") == 0) continue;
        if (count == cap) {
            cap *= 2;
            char **next = (char **)realloc(flat, cap * sizeof(char *));
            if (!next) break;
            flat = next;
        }
        flat[count++] = ez_fs_copy_str(data.cFileName);
    } while (FindNextFileA(handle, &data) != 0);
    FindClose(handle);

    int64_t page_count = count == 0 ? 0 : (int64_t)((count + 7) / 8);
    char ***pages = page_count == 0 ? NULL : (char ***)calloc((size_t)page_count, sizeof(char **));
    if (page_count > 0 && !pages) {
        for (size_t i = 0; i < count; ++i) free(flat[i]);
        free(flat);
        return (StrList){0};
    }
    for (int64_t page = 0; page < page_count; ++page) {
        pages[page] = (char **)calloc(8, sizeof(char *));
        if (!pages[page]) continue;
        for (int64_t offset = 0; offset < 8; ++offset) {
            size_t idx = (size_t)(page * 8 + offset);
            if (idx < count) pages[page][offset] = flat[idx];
        }
    }
    free(flat);
    return (StrList){pages, (int64_t)count, page_count * 8, page_count};
#else
    DIR *dir = opendir(path);
    if (!dir) return (StrList){0};
    size_t count = 0;
    size_t cap = 8;
    char **flat = (char **)calloc(cap, sizeof(char *));
    if (!flat) {
        closedir(dir);
        return (StrList){0};
    }
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;
        if (count == cap) {
            cap *= 2;
            char **next = (char **)realloc(flat, cap * sizeof(char *));
            if (!next) break;
            flat = next;
        }
        flat[count++] = ez_fs_copy_str(entry->d_name);
    }
    closedir(dir);
    int64_t page_count = count == 0 ? 0 : (int64_t)((count + 7) / 8);
    char ***pages = page_count == 0 ? NULL : (char ***)calloc((size_t)page_count, sizeof(char **));
    if (page_count > 0 && !pages) {
        for (size_t i = 0; i < count; ++i) free(flat[i]);
        free(flat);
        return (StrList){0};
    }
    for (int64_t page = 0; page < page_count; ++page) {
        pages[page] = (char **)calloc(8, sizeof(char *));
        if (!pages[page]) continue;
        for (int64_t offset = 0; offset < 8; ++offset) {
            size_t idx = (size_t)(page * 8 + offset);
            if (idx < count) pages[page][offset] = flat[idx];
        }
    }
    free(flat);
    return (StrList){pages, (int64_t)count, page_count * 8, page_count};
#endif
}

static void ez_fs_ensure_parent(const char *path) {
    if (!path) return;
    char *copy = ez_fs_copy_str(path);
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

static bool ez_fs_write(const char *path, const Blob *content, const char *mode) {
    if (!content) return false;
    char *real_path = ez_fs_path(path);
    if (!real_path) return false;
    ez_fs_ensure_parent(real_path);
    FILE *file = fopen(real_path, mode);
    free(real_path);
    if (!file) return false;
    size_t written = fwrite(content->data, 1, (size_t)content->size, file);
    fclose(file);
    return written == (size_t)content->size;
}

bool writeFile(const char *path, const Blob *content) {
    return ez_fs_write(path, content, "wb");
}

bool appendFile(const char *path, const Blob *content) {
    return ez_fs_write(path, content, "ab");
}

bool removeFile(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return false;
    bool ok = remove(real_path) == 0;
    free(real_path);
    return ok;
}

bool ez_std_mkdir(const char *path) EZ_ABI_NAME(mkdir);
bool ez_std_mkdir(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return false;
    ez_fs_ensure_parent(real_path);
    bool ok = ez_fs_mkdir_one(real_path);
    free(real_path);
    return ok;
}

bool removeDir(const char *path, bool recursive) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return false;
#if defined(_WIN32)
    bool ok = recursive ? ez_fs_remove_tree(real_path) : (_rmdir(real_path) == 0);
#else
    bool ok = recursive ? ez_fs_remove_tree(real_path) : (rmdir(real_path) == 0);
#endif
    free(real_path);
    return ok;
}

StrList listDir(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return (StrList){0};
    StrList items = ez_fs_list_dir(real_path);
    free(real_path);
    return items;
}

bool exists(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return false;
#if defined(_WIN32)
    bool ok = _access(real_path, 0) == 0;
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
    struct _stat64 st;
    bool ok = _stat64(real_path, &st) == 0 && (st.st_mode & _S_IFDIR) != 0;
#else
    struct stat st;
    bool ok = lstat(real_path, &st) == 0 && S_ISDIR(st.st_mode);
#endif
    free(real_path);
    return ok;
}

OptFileStat ez_std_stat(const char *path) EZ_ABI_NAME(stat);
OptFileStat ez_std_stat(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return (OptFileStat){false, {0}};
#if defined(_WIN32)
    struct _stat64 st;
    if (_stat64(real_path, &st) != 0) {
        free(real_path);
        return (OptFileStat){false, {0}};
    }
    free(real_path);
    FileStat result;
    result.size = (int64_t)st.st_size;
    result.isDir = (st.st_mode & _S_IFDIR) != 0;
    result.modified = (int64_t)st.st_mtime * 1000;
    result.created = (int64_t)st.st_ctime * 1000;
    return (OptFileStat){true, result};
#else
    struct stat st;
    if (lstat(real_path, &st) != 0) {
        free(real_path);
        return (OptFileStat){false, {0}};
    }
    free(real_path);
    FileStat result;
    result.size = (int64_t)st.st_size;
    result.isDir = S_ISDIR(st.st_mode);
    result.modified = (int64_t)st.st_mtime * 1000;
#if defined(__APPLE__)
    result.created = (int64_t)st.st_birthtime * 1000;
#else
    result.created = (int64_t)st.st_ctime * 1000;
#endif
    return (OptFileStat){true, result};
#endif
}

const char *absPath(const char *path) {
    char *real_path = ez_fs_path(path);
    if (!real_path) return ez_fs_copy_str("");
#if defined(_WIN32)
    char *resolved = _fullpath(NULL, real_path, 0);
    if (resolved) {
        free(real_path);
        return resolved;
    }
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
