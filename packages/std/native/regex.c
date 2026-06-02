// EzLang std/regex 原生封装层

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if !defined(_WIN32)
#include <regex.h>
#endif

typedef struct {
    char ***pages;
    int64_t length;
    int64_t capacity;
    int64_t page_count;
} StrList;

typedef struct {
    const char *pattern;
    int32_t flags;
    bool ok;
} Regex;

typedef struct {
    int64_t start;
    int64_t end;
    const char *text;
    StrList groups;
} RegexMatch;

typedef struct { bool ok; RegexMatch value; } OptRegexMatch;

static char *ez_strdup_range(const char *src, size_t len) {
    char *out = (char *)malloc(len + 1);
    if (!out) return NULL;
    if (len > 0 && src) memcpy(out, src, len);
    out[len] = '\0';
    return out;
}

static char *ez_strdup_safe(const char *src) {
    if (!src) src = "";
    return ez_strdup_range(src, strlen(src));
}

static StrList ez_make_str_list(char **items, size_t count) {
    int64_t page_count = count == 0 ? 0 : (int64_t)((count + 7) / 8);
    char ***pages = page_count == 0 ? NULL : (char ***)calloc((size_t)page_count, sizeof(char **));
    if (page_count > 0 && !pages) return (StrList){0};
    for (int64_t page = 0; page < page_count; ++page) {
        pages[page] = (char **)calloc(8, sizeof(char *));
        if (!pages[page]) continue;
        for (int64_t offset = 0; offset < 8; ++offset) {
            size_t idx = (size_t)(page * 8 + offset);
            pages[page][offset] = idx < count ? items[idx] : NULL;
        }
    }
    return (StrList){pages, (int64_t)count, page_count * 8, page_count};
}

static int ez_regex_cflags(int32_t flags) {
#if defined(_WIN32)
    (void)flags;
    return 0;
#else
    int cflags = REG_EXTENDED;
    if ((flags & 1) != 0) cflags |= REG_ICASE;
    if ((flags & 2) == 0) cflags |= REG_NEWLINE;
    return cflags;
#endif
}

#if !defined(_WIN32)
static bool ez_compile(const Regex *regex, regex_t *compiled) {
    if (!regex || !regex->ok || !regex->pattern) return false;
    return regcomp(compiled, regex->pattern, ez_regex_cflags(regex->flags)) == 0;
}
#endif

Regex regexCompile(const char *pattern, int32_t flags) {
    if (!pattern) pattern = "";
#if defined(_WIN32)
    return (Regex){ez_strdup_safe(pattern), flags, false};
#else
    regex_t compiled;
    bool ok = regcomp(&compiled, pattern, ez_regex_cflags(flags)) == 0;
    if (ok) regfree(&compiled);
    return (Regex){ez_strdup_safe(pattern), flags, ok};
#endif
}

bool regexIsValid(const Regex *regex) {
    return regex && regex->ok;
}

bool regexTest(const Regex *regex, const char *input) {
    if (!input) input = "";
#if defined(_WIN32)
    (void)regex;
    return false;
#else
    regex_t compiled;
    if (!ez_compile(regex, &compiled)) return false;
    int result = regexec(&compiled, input, 0, NULL, 0);
    regfree(&compiled);
    return result == 0;
#endif
}

static OptRegexMatch ez_find_impl(const Regex *regex, const char *input) {
    if (!input) input = "";
#if defined(_WIN32)
    (void)regex;
    return (OptRegexMatch){false, {0}};
#else
    regex_t compiled;
    if (!ez_compile(regex, &compiled)) return (OptRegexMatch){false, {0}};
    size_t group_count = compiled.re_nsub + 1;
    regmatch_t *matches = (regmatch_t *)calloc(group_count, sizeof(regmatch_t));
    if (!matches) {
        regfree(&compiled);
        return (OptRegexMatch){false, {0}};
    }
    int result = regexec(&compiled, input, group_count, matches, 0);
    if (result != 0 || matches[0].rm_so < 0) {
        free(matches);
        regfree(&compiled);
        return (OptRegexMatch){false, {0}};
    }

    size_t capture_count = group_count > 0 ? group_count - 1 : 0;
    char **groups = capture_count == 0 ? NULL : (char **)calloc(capture_count, sizeof(char *));
    if (capture_count > 0 && !groups) {
        free(matches);
        regfree(&compiled);
        return (OptRegexMatch){false, {0}};
    }
    for (size_t i = 0; i < capture_count; ++i) {
        regmatch_t group = matches[i + 1];
        groups[i] = group.rm_so >= 0 ? ez_strdup_range(input + group.rm_so, (size_t)(group.rm_eo - group.rm_so)) : ez_strdup_safe("");
    }
    RegexMatch match;
    match.start = matches[0].rm_so;
    match.end = matches[0].rm_eo;
    match.text = ez_strdup_range(input + matches[0].rm_so, (size_t)(matches[0].rm_eo - matches[0].rm_so));
    match.groups = ez_make_str_list(groups, capture_count);
    free(groups);
    free(matches);
    regfree(&compiled);
    return (OptRegexMatch){true, match};
#endif
}

OptRegexMatch regexFind(const Regex *regex, const char *input) {
    return ez_find_impl(regex, input);
}

StrList regexFindAll(const Regex *regex, const char *input) {
    if (!input) input = "";
#if defined(_WIN32)
    (void)regex;
    return (StrList){0};
#else
    regex_t compiled;
    if (!ez_compile(regex, &compiled)) return (StrList){0};
    size_t cap = 8;
    size_t count = 0;
    char **items = (char **)calloc(cap, sizeof(char *));
    if (!items) {
        regfree(&compiled);
        return (StrList){0};
    }
    const char *cursor = input;
    int64_t offset = 0;
    while (*cursor) {
        regmatch_t match;
        if (regexec(&compiled, cursor, 1, &match, 0) != 0 || match.rm_so < 0) break;
        if (count == cap) {
            cap *= 2;
            char **next = (char **)realloc(items, cap * sizeof(char *));
            if (!next) break;
            items = next;
        }
        items[count++] = ez_strdup_range(cursor + match.rm_so, (size_t)(match.rm_eo - match.rm_so));
        int64_t advance = match.rm_eo > 0 ? match.rm_eo : match.rm_so + 1;
        cursor += advance;
        offset += advance;
        (void)offset;
    }
    StrList result = ez_make_str_list(items, count);
    free(items);
    regfree(&compiled);
    return result;
#endif
}

const char *regexReplace(const Regex *regex, const char *input, const char *replacement) {
    if (!input) input = "";
    if (!replacement) replacement = "";
    OptRegexMatch found = ez_find_impl(regex, input);
    if (!found.ok) return ez_strdup_safe(input);
    size_t input_len = strlen(input);
    size_t repl_len = strlen(replacement);
    size_t out_len = (size_t)found.value.start + repl_len + (input_len - (size_t)found.value.end);
    char *out = (char *)malloc(out_len + 1);
    if (!out) return NULL;
    memcpy(out, input, (size_t)found.value.start);
    memcpy(out + found.value.start, replacement, repl_len);
    strcpy(out + found.value.start + repl_len, input + found.value.end);
    return out;
}

StrList regexSplit(const Regex *regex, const char *input) {
    if (!input) input = "";
#if defined(_WIN32)
    (void)regex;
    char *items[1] = {ez_strdup_safe(input)};
    return ez_make_str_list(items, 1);
#else
    regex_t compiled;
    if (!ez_compile(regex, &compiled)) {
        char *items[1] = {ez_strdup_safe(input)};
        return ez_make_str_list(items, 1);
    }
    size_t cap = 8;
    size_t count = 0;
    char **items = (char **)calloc(cap, sizeof(char *));
    if (!items) {
        regfree(&compiled);
        return (StrList){0};
    }
    const char *cursor = input;
    while (true) {
        regmatch_t match;
        int result = regexec(&compiled, cursor, 1, &match, 0);
        if (result != 0 || match.rm_so < 0) break;
        if (count == cap) {
            cap *= 2;
            char **next = (char **)realloc(items, cap * sizeof(char *));
            if (!next) break;
            items = next;
        }
        items[count++] = ez_strdup_range(cursor, (size_t)match.rm_so);
        int64_t advance = match.rm_eo > 0 ? match.rm_eo : match.rm_so + 1;
        cursor += advance;
        if (!*cursor) break;
    }
    if (count == cap) {
        cap += 1;
        char **next = (char **)realloc(items, cap * sizeof(char *));
        if (next) items = next;
    }
    items[count++] = ez_strdup_safe(cursor);
    StrList result = ez_make_str_list(items, count);
    free(items);
    regfree(&compiled);
    return result;
#endif
}
