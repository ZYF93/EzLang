"""允许通过 `python -m lsp` 启动 EzLang LSP。"""

from .server import main


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

