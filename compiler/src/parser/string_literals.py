"""EzLang 字符串字面量解码工具。"""

from __future__ import annotations


def decode_string_literal_token(token_text: str) -> str:
    """把包含引号的 STRING_LITERAL token 解码为运行时字符串。"""
    if len(token_text) < 2 or token_text[0] != '"' or token_text[-1] != '"':
        return token_text
    return decode_string_literal_body(token_text[1:-1])


def decode_string_literal_body(body: str) -> str:
    """解码字符串字面量主体中的转义序列。"""
    out: list[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        i += 1
        if i >= len(body):
            out.append("\\")
            break

        esc = body[i]
        i += 1
        simple = {
            '"': '"',
            "'": "'",
            "\\": "\\",
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "b": "\b",
            "f": "\f",
            "v": "\v",
            "0": "\0",
        }
        if esc in simple:
            out.append(simple[esc])
            continue
        if esc == "x" and i + 2 <= len(body):
            digits = body[i:i + 2]
            if _is_hex(digits):
                out.append(chr(int(digits, 16)))
                i += 2
                continue
        if esc == "u" and i + 4 <= len(body):
            digits = body[i:i + 4]
            if _is_hex(digits):
                codepoint = int(digits, 16)
                i += 4
                if 0xD800 <= codepoint <= 0xDBFF and body[i:i + 2] == "\\u" and i + 6 <= len(body):
                    low_digits = body[i + 2:i + 6]
                    if _is_hex(low_digits):
                        low = int(low_digits, 16)
                        if 0xDC00 <= low <= 0xDFFF:
                            codepoint = 0x10000 + ((codepoint - 0xD800) << 10) + (low - 0xDC00)
                            i += 6
                if 0xD800 <= codepoint <= 0xDFFF or codepoint > 0x10FFFF:
                    out.append("\uFFFD")
                else:
                    out.append(chr(codepoint))
                continue
        if esc == "U" and i + 8 <= len(body):
            digits = body[i:i + 8]
            if _is_hex(digits):
                codepoint = int(digits, 16)
                if 0xD800 <= codepoint <= 0xDFFF or codepoint > 0x10FFFF:
                    out.append("\uFFFD")
                else:
                    out.append(chr(codepoint))
                i += 8
                continue

        # 语法当前允许任意反斜杠转义；未知转义保持转义后的字符，避免悄悄注入反斜杠。
        out.append(esc)

    return "".join(out)


def _is_hex(text: str) -> bool:
    return bool(text) and all(ch in "0123456789abcdefABCDEF" for ch in text)
