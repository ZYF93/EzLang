#define EZ_REGEX_FORCE_PORTABLE 1

#include <stdio.h>
#include <string.h>

#include "../../../packages/std/native/regex.c"

static const char *list_get(StrList list, int64_t index) {
    int64_t page = index / 8;
    int64_t offset = index % 8;
    if (index < 0 || index >= list.length || !list.pages || !list.pages[page]) return "";
    return list.pages[page][offset] ? list.pages[page][offset] : "";
}

static int expect_str(const char *actual, const char *expected) {
    return actual && strcmp(actual, expected) == 0;
}

int main(void) {
    Regex word = regexCompile("([[:alpha:]]+)", 0);
    if (!regexIsValid(&word)) return 1;
    if (!regexTest(&word, "EzLang 42")) return 2;

    OptRegexMatch found = regexFind(&word, "EzLang 42");
    if (!found.ok) return 3;
    if (found.value.start != 0 || found.value.end != 6) return 4;
    if (!expect_str(found.value.text, "EzLang")) return 5;
    if (found.value.groups.length != 1 || !expect_str(list_get(found.value.groups, 0), "EzLang")) return 6;

    Regex utf = regexCompile("(Ez)", 0);
    OptRegexMatch utf_found = regexFind(&utf, "中Ez");
    if (!utf_found.ok) return 14;
    if (utf_found.value.start != 3 || utf_found.value.end != 5) return 15;
    if (!expect_str(utf_found.value.text, "Ez")) return 16;
    if (utf_found.value.groups.length != 1 || !expect_str(list_get(utf_found.value.groups, 0), "Ez")) return 17;

    StrList all = regexFindAll(&word, "one two three");
    if (all.length != 3 || !expect_str(list_get(all, 2), "three")) return 7;

    Regex first_digit = regexCompile("[[:digit:]]", 0);
    const char *first = regexReplace(&first_digit, "a1b2c3", "#");
    if (!expect_str(first, "a#b2c3")) return 8;

    Regex upper = regexCompile("([A-Z]+)", 0);
    const char *literal = regexReplace(&upper, "ABC DEF", "$1");
    if (!expect_str(literal, "$1 DEF")) return 18;

    Regex line_start = regexCompile("^b", 2);
    if (!regexTest(&line_start, "a\nb")) return 20;
    Regex string_start = regexCompile("^b", 0);
    if (regexTest(&string_start, "a\nb")) return 21;
    Regex dot = regexCompile("a.b", 0);
    if (!regexTest(&dot, "a b") || regexTest(&dot, "a\nb")) return 22;

    Regex all_digits = regexCompile("[[:digit:]]", 4);
    const char *replaced = regexReplace(&all_digits, "a1b2c3", "#");
    if (!expect_str(replaced, "a#b#c#")) return 9;

    Regex exact_repeat = regexCompile("ab{2}c", 0);
    if (!regexIsValid(&exact_repeat)) return 23;
    if (!regexTest(&exact_repeat, "abbc") || regexTest(&exact_repeat, "abc")) return 24;

    Regex ranged_repeat = regexCompile("ab{2,4}c", 0);
    if (!regexIsValid(&ranged_repeat)) return 25;
    if (!regexTest(&ranged_repeat, "abbc") || !regexTest(&ranged_repeat, "abbbbc") || regexTest(&ranged_repeat, "abbbbbc")) return 26;

    Regex open_repeat = regexCompile("ab{2,}c", 0);
    if (!regexIsValid(&open_repeat)) return 27;
    if (!regexTest(&open_repeat, "abbc") || !regexTest(&open_repeat, "abbbbbc") || regexTest(&open_repeat, "abc")) return 28;

    Regex repeat_group = regexCompile("(ab){2,3}", 0);
    if (!regexIsValid(&repeat_group)) return 29;
    OptRegexMatch repeated_group = regexFind(&repeat_group, "zababx");
    if (!repeated_group.ok || !expect_str(repeated_group.value.text, "abab") || !expect_str(list_get(repeated_group.value.groups, 0), "ab")) return 30;

    Regex invalid_repeat = regexCompile("ab{4,2}c", 0);
    if (regexIsValid(&invalid_repeat)) return 31;

    Regex nested_repeat = regexCompile("(a+)+$", 0);
    if (regexIsValid(&nested_repeat) || regexTest(&nested_repeat, "aaaaaaaaaaaaaaaa!")) return 32;
    Regex repeated_alt = regexCompile("(a|aa)+$", 0);
    if (regexIsValid(&repeated_alt)) return 33;
    Regex huge_repeat = regexCompile("a{0,2048}", 0);
    if (regexIsValid(&huge_repeat)) return 34;

    Regex comma = regexCompile(",", 4);
    StrList parts = regexSplit(&comma, "a,b,c");
    if (parts.length != 3 || !expect_str(list_get(parts, 1), "b")) return 10;

    Regex captured_comma = regexCompile("([,])", 4);
    StrList captured_parts = regexSplit(&captured_comma, "a,b,c");
    if (captured_parts.length != 3 || !expect_str(list_get(captured_parts, 1), "b")) return 19;

    Regex boundary = regexCompile("(^|$)", 4);
    const char *bounded = regexReplace(&boundary, "ab", "|");
    if (!expect_str(bounded, "|ab|")) return 11;

    Regex start = regexCompile("^", 0);
    StrList anchors = regexFindAll(&start, "abc");
    if (anchors.length != 1 || !expect_str(list_get(anchors, 0), "")) return 12;

    Regex invalid = regexCompile("(", 0);
    if (regexIsValid(&invalid)) return 13;

    puts(found.value.text);
    puts(replaced);
    puts(bounded);
    return 0;
}
