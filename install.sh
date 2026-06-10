#!/usr/bin/env sh
set -eu

# 安装 EzLang CLI 与编译器。
# 默认安装到 ~/.ezlang；可通过 EZLANG_INSTALL_DIR 覆盖。
# 用法：
#   sh install.sh                         # 从官方远程仓库 clone/update 后安装
#   sh install.sh --local                 # 从当前源码目录安装（开发用）
#   EZLANG_REPO_URL=<git-url> sh install.sh  # 使用镜像仓库安装
#   EZLANG_REGISTER_PATH=0 sh install.sh     # 不修改 shell 配置文件

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
DEFAULT_REPO_URL="https://github.com/ZYF93/EzLang.git"
PREFIX=${EZLANG_INSTALL_DIR:-"$HOME/.ezlang"}
PYTHON_BIN=${PYTHON:-python3}
VENV_DIR="$PREFIX/venv"
BIN_DIR="$PREFIX/bin"
SRC_DIR="$PREFIX/src"
INSTALL_ARG=${1:-}
USE_LOCAL=0
if [ "$INSTALL_ARG" = "--local" ]; then
    USE_LOCAL=1
elif [ -n "$INSTALL_ARG" ]; then
    EZLANG_REPO_URL=$INSTALL_ARG
fi
REPO_URL=${EZLANG_REPO_URL:-$DEFAULT_REPO_URL}
REGISTER_PATH=${EZLANG_REGISTER_PATH:-1}

die() {
    echo "error: $*" >&2
    exit 1
}

warn() {
    echo "warning: $*" >&2
}

require_python() {
    if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
        die "未找到 Python 3.9+。请先安装 Python：macOS 可执行 \`brew install python\`，Ubuntu/Debian 可执行 \`sudo apt install python3 python3-venv python3-pip\`，然后重试。"
    fi
    if ! PYTHON_VERSION=$("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:3]))); raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null); then
        die "检测到的 Python 版本不满足要求：$PYTHON_VERSION。EzLang 编译器需要 Python 3.9+。"
    fi
}

require_native_linker() {
    if ! command -v cc >/dev/null 2>&1; then
        die "未找到 C 编译器 \`cc\`。EzLang 本机目标链接和 C extern 编译需要它：macOS 可执行 \`xcode-select --install\`，Ubuntu/Debian 可执行 \`sudo apt install build-essential\`。"
    fi
}

emcc_status() {
    if command -v emcc >/dev/null 2>&1; then
        echo "已检测到 emcc"
    else
        echo "未检测到 emcc；只有构建 os=\"emcc\" / wasm32 目标时才需要 Emscripten SDK"
    fi
}

require_python
require_native_linker
if [ -n "${EZLANG_PROFILE:-}" ]; then
    PROFILE_FILE=$EZLANG_PROFILE
else
    case "${SHELL:-}" in
        */zsh) PROFILE_FILE="$HOME/.zprofile" ;;
        */bash)
            if [ -f "$HOME/.bash_profile" ]; then
                PROFILE_FILE="$HOME/.bash_profile"
            else
                PROFILE_FILE="$HOME/.bashrc"
            fi
            ;;
        *) PROFILE_FILE="$HOME/.profile" ;;
    esac
fi

if [ "$USE_LOCAL" = "1" ]; then
    SRC_DIR="$SCRIPT_DIR"
else
    if ! command -v git >/dev/null 2>&1; then
        die "安装远程 EzLang 需要 git。请先安装 git 后重试。"
    fi
    if [ -d "$SRC_DIR/.git" ]; then
        if git -C "$SRC_DIR" remote get-url origin >/dev/null 2>&1; then
            git -C "$SRC_DIR" remote set-url origin "$REPO_URL"
        else
            git -C "$SRC_DIR" remote add origin "$REPO_URL"
        fi
        git -C "$SRC_DIR" fetch --tags --prune
        git -C "$SRC_DIR" pull --ff-only
    elif [ -e "$SRC_DIR" ]; then
        echo "error: $SRC_DIR 已存在但不是 git 仓库" >&2
        exit 1
    else
        mkdir -p "$PREFIX"
        git clone "$REPO_URL" "$SRC_DIR"
    fi
fi

mkdir -p "$BIN_DIR"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install -e "$SRC_DIR"
"$VENV_DIR/bin/python" -c "import llvmlite.binding" >/dev/null 2>&1 || die "llvmlite 安装或加载失败。对象文件生成依赖 llvmlite 自带的 LLVM binding，请检查 pip 安装输出。"

cat > "$BIN_DIR/ez" <<EOF
#!/usr/bin/env sh
exec "$VENV_DIR/bin/ez" "\$@"
EOF
chmod +x "$BIN_DIR/ez"

"$BIN_DIR/ez" --version >/dev/null
if [ -f "$SRC_DIR/project.toml" ]; then
    "$BIN_DIR/ez" install --project "$SRC_DIR/project.toml" >/dev/null
fi
VERIFY_DIR="$PREFIX/install-check"
mkdir -p "$VERIFY_DIR/src"
cat > "$VERIFY_DIR/project.toml" <<EOF
[project]
name = "install_check"
version = "0.0.0"
main = "src/main.ez"
public = false
optimize = 0

[[output]]
arch = "$(uname -m | sed 's/^arm64$/aarch64/; s/^amd64$/x86_64/')"
os = "$(uname -s | tr '[:upper:]' '[:lower:]' | sed 's/^darwin$/macos/')"
dir = "dist/native"
EOF
cat > "$VERIFY_DIR/src/main.ez" <<'EOF'
let $code: I32 = 0;
$code = $code + 0;
EOF
"$BIN_DIR/ez" build --project "$VERIFY_DIR/project.toml" >/dev/null

if [ "$REGISTER_PATH" != "0" ]; then
    mkdir -p "$(dirname "$PROFILE_FILE")"
    touch "$PROFILE_FILE"
    PATH_LINE="export PATH=\"$BIN_DIR:\$PATH\""
    if ! grep -F "$BIN_DIR" "$PROFILE_FILE" >/dev/null 2>&1; then
        {
            echo ""
            echo "# EzLang CLI"
            echo "$PATH_LINE"
        } >> "$PROFILE_FILE"
        PATH_STATUS="已写入 $PROFILE_FILE"
    else
        PATH_STATUS="$PROFILE_FILE 已包含 $BIN_DIR"
    fi
else
    PATH_STATUS="已跳过 PATH 注册"
fi

echo "EzLang 已安装到 $PREFIX"
echo "源码目录: $SRC_DIR"
echo "安装校验: ez --version、ez install 与 ez build 通过"
echo "PATH 注册: $PATH_STATUS"
echo "Python: $PYTHON_VERSION"
echo "LLVM: 使用 Python 包 llvmlite 提供的 LLVM binding，无需单独安装系统 LLVM"
echo "Emscripten: $(emcc_status)"
echo "例如: export PATH=\"$BIN_DIR:\$PATH\""
