"""
EzLang 编译器错误处理系统。
提供带源码位置信息的错误报告，支持格式化输出到终端。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Severity(Enum):
    """错误严重级别。"""
    ERROR = auto()
    WARNING = auto()
    INFO = auto()

    def label(self) -> str:
        return self.name.lower()

    def color_code(self) -> str:
        """ANSI 颜色码。"""
        return {
            Severity.ERROR: "\033[1;31m",    # 红色加粗
            Severity.WARNING: "\033[1;33m",  # 黄色加粗
            Severity.INFO: "\033[1;36m",     # 青色加粗
        }[self]


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


@dataclass
class SourceLocation:
    """源码位置信息。"""
    file: str
    line: int          # 1-indexed
    column: int        # 0-indexed
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.column}"


@dataclass
class CompileError:
    """
    带位置信息的编译错误。

    格式化输出示例:
        examples/hello.ez:10:5 - error: undeclared variable 'x'
         10 |     let y = x + 1;
            |             ^
    """
    message: str
    location: Optional[SourceLocation] = None
    severity: Severity = Severity.ERROR
    hint: Optional[str] = None
    source_line: Optional[str] = None

    def format(self, use_color: bool = True) -> str:
        """格式化为可读的错误信息字符串。"""
        parts: list[str] = []

        # 位置 + 严重级别 + 消息
        loc_str = str(self.location) if self.location else "<unknown>"
        if use_color:
            sev_color = self.severity.color_code()
            parts.append(
                f"{BOLD}{loc_str}{RESET} - "
                f"{sev_color}{self.severity.label()}{RESET}: "
                f"{self.message}"
            )
        else:
            parts.append(
                f"{loc_str} - {self.severity.label()}: {self.message}"
            )

        # 源码行 + 指示箭头
        if self.source_line is not None and self.location is not None:
            line_no = str(self.location.line)
            padding = " " * len(line_no)

            if use_color:
                parts.append(f" {DIM}{line_no} |{RESET} {self.source_line}")
                caret_pad = " " * self.location.column
                parts.append(f" {padding} | {caret_pad}{sev_color}^{RESET}")
            else:
                parts.append(f" {line_no} | {self.source_line}")
                caret_pad = " " * self.location.column
                parts.append(f" {padding} | {caret_pad}^")

        # 提示
        if self.hint:
            prefix = f"{DIM}hint:{RESET} " if use_color else "hint: "
            parts.append(f" {prefix}{self.hint}")

        return "\n".join(parts)

    def __str__(self) -> str:
        return self.format(use_color=False)


class ErrorCollector:
    """
    收集编译过程中产生的所有错误/警告，支持批量报告。
    """

    def __init__(self, source_lines: Optional[list[str]] = None, file: str = "<stdin>"):
        self._errors: list[CompileError] = []
        self._source_lines = source_lines or []
        self._file = file

    @property
    def has_errors(self) -> bool:
        return any(e.severity == Severity.ERROR for e in self._errors)

    @property
    def error_count(self) -> int:
        return sum(1 for e in self._errors if e.severity == Severity.ERROR)

    @property
    def errors(self) -> list[CompileError]:
        return list(self._errors)

    def _get_source_line(self, line: int) -> Optional[str]:
        """获取源码的指定行（1-indexed）。"""
        if 0 < line <= len(self._source_lines):
            return self._source_lines[line - 1].rstrip("\n\r")
        return None

    def error(self, message: str, line: int = 0, column: int = 0,
              hint: Optional[str] = None) -> CompileError:
        """报告一个编译错误。"""
        loc = SourceLocation(file=self._file, line=line, column=column)
        err = CompileError(
            message=message,
            location=loc,
            severity=Severity.ERROR,
            hint=hint,
            source_line=self._get_source_line(line),
        )
        self._errors.append(err)
        return err

    def warning(self, message: str, line: int = 0, column: int = 0,
                hint: Optional[str] = None) -> CompileError:
        """报告一个编译警告。"""
        loc = SourceLocation(file=self._file, line=line, column=column)
        err = CompileError(
            message=message,
            location=loc,
            severity=Severity.WARNING,
            hint=hint,
            source_line=self._get_source_line(line),
        )
        self._errors.append(err)
        return err

    def report(self, stream=None, use_color: bool = True) -> None:
        """将所有错误/警告输出到指定流。"""
        stream = stream or sys.stderr
        for err in self._errors:
            print(err.format(use_color=use_color), file=stream)
            print(file=stream)

        if self.has_errors:
            count = self.error_count
            msg = f"编译失败: {count} 个错误"
            if use_color:
                print(f"{BOLD}\033[1;31m{msg}{RESET}", file=stream)
            else:
                print(msg, file=stream)
