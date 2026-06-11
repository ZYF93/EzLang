#!/usr/bin/env sh
set -eu

# 安装 EzLang CLI 与编译器。
# 默认安装到 ~/.ezlang；可通过 EZLANG_INSTALL_DIR 覆盖。
# 用法：
#   sh install.sh                         # 从官方远程仓库 clone/update 后安装
#   sh install.sh --local                 # 从当前源码目录安装（开发用）
#   EZLANG_INSTALL_DEPS=1 sh install.sh    # 尝试用系统包管理器安装缺失的基础依赖
#   EZLANG_REGISTER_PATH=0 sh install.sh   # 不修改 shell 配置文件

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
DEFAULT_REPO_URL="https://github.com/ZYF93/EzLang.git"
PREFIX=${EZLANG_INSTALL_DIR:-"$HOME/.ezlang"}
PYTHON_BIN=${PYTHON:-python3}
VENV_DIR="$PREFIX/venv"
BIN_DIR="$PREFIX/bin"
SRC_DIR="$PREFIX/src"
PROFILE_SNIPPET="$PREFIX/env"
INSTALL_ARG=${1:-}
USE_LOCAL=0
arg_error() {
    echo "error: $*" >&2
    exit 1
}

if [ "$INSTALL_ARG" = "--local" ]; then
    USE_LOCAL=1
elif [ -n "$INSTALL_ARG" ]; then
    arg_error "不支持自定义仓库参数：${INSTALL_ARG}。安装脚本固定使用 ${DEFAULT_REPO_URL}；开发安装请使用 --local。"
fi
REPO_URL=$DEFAULT_REPO_URL
REGISTER_PATH=${EZLANG_REGISTER_PATH:-1}
INSTALL_DEPS=${EZLANG_INSTALL_DEPS:-0}

die() {
    echo "error: $*" >&2
    exit 1
}

warn() {
    echo "warning: $*" >&2
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

package_manager() {
    if command_exists brew; then echo brew; return; fi
    if command_exists apt-get; then echo apt; return; fi
    if command_exists dnf; then echo dnf; return; fi
    if command_exists yum; then echo yum; return; fi
    if command_exists pacman; then echo pacman; return; fi
    echo ""
}

install_packages() {
    pm=$(package_manager)
    case "$pm" in
        brew) brew install "$@" ;;
        apt) sudo apt-get update && sudo apt-get install -y "$@" ;;
        dnf) sudo dnf install -y "$@" ;;
        yum) sudo yum install -y "$@" ;;
        pacman) sudo pacman -Sy --needed --noconfirm "$@" ;;
        *) return 1 ;;
    esac
}

install_dependency() {
    tool=$1
    pm=$(package_manager)
    case "$pm:$tool" in
        brew:python) install_packages python ;;
        brew:git) install_packages git ;;
        brew:cc) xcode-select --install ;;
        apt:python) install_packages python3 python3-venv python3-pip ;;
        apt:git) install_packages git ;;
        apt:cc) install_packages build-essential ;;
        dnf:python) install_packages python3 python3-pip ;;
        dnf:git) install_packages git ;;
        dnf:cc) install_packages gcc make ;;
        yum:python) install_packages python3 python3-pip ;;
        yum:git) install_packages git ;;
        yum:cc) install_packages gcc make ;;
        pacman:python) install_packages python python-pip ;;
        pacman:git) install_packages git ;;
        pacman:cc) install_packages base-devel ;;
        *) return 1 ;;
    esac
}

dependency_hint() {
    tool=$1
    case "$tool" in
        python)
            echo "macOS: brew install python；Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip；Fedora: sudo dnf install python3 python3-pip；Arch: sudo pacman -S python python-pip" ;;
        git)
            echo "macOS: xcode-select --install 或 brew install git；Ubuntu/Debian: sudo apt install git；Fedora: sudo dnf install git；Arch: sudo pacman -S git" ;;
        cc)
            echo "macOS: xcode-select --install；Ubuntu/Debian: sudo apt install build-essential；Fedora: sudo dnf install gcc make；Arch: sudo pacman -S base-devel" ;;
        emcc)
            echo "Emscripten 只在构建 os=\"emcc\" / wasm32 时需要：git clone https://github.com/emscripten-core/emsdk.git && cd emsdk && ./emsdk install latest && ./emsdk activate latest && . ./emsdk_env.sh" ;;
        android)
            echo "Android 目标需要 Android NDK，并在 project.toml 的 output.sdk 指向 NDK 根目录。" ;;
        ios)
            echo "iOS 目标需要 macOS + Xcode Command Line Tools，并在 project.toml 的 output.sdk 指向 Xcode/SDK 根目录。" ;;
    esac
}

try_install_dependency() {
    tool=$1
    if [ "$INSTALL_DEPS" != "1" ]; then
        return 1
    fi
    pm=$(package_manager)
    if [ -z "$pm" ]; then
        return 1
    fi
    echo "正在尝试安装 $tool 依赖（包管理器：$pm）..."
    install_dependency "$tool"
}

require_python() {
    if ! command_exists "$PYTHON_BIN"; then
        try_install_dependency python || die "未找到 Python 3.9+。请先安装 Python：$(dependency_hint python)"
    fi
    if ! PYTHON_VERSION=$("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:3]))); raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null); then
        die "检测到的 Python 版本不满足要求：$PYTHON_VERSION。EzLang 编译器需要 Python 3.9+。"
    fi
    if ! "$PYTHON_BIN" -c 'import venv' >/dev/null 2>&1; then
        try_install_dependency python || die "当前 Python 缺少 venv 模块。请安装 Python venv 支持：$(dependency_hint python)"
    fi
}

require_git() {
    if command_exists git; then
        return
    fi
    try_install_dependency git || die "安装远程 EzLang 需要 git。请先安装 git：$(dependency_hint git)"
}

require_native_linker() {
    if ! command_exists cc; then
        try_install_dependency cc || die "未找到 C 编译器 \`cc\`。EzLang 本机目标链接和 C extern 编译需要它：$(dependency_hint cc)"
    fi
}

emcc_status() {
    if command_exists emcc; then
        echo "已检测到 emcc"
    else
        echo "未检测到 emcc；只有构建 os=\"emcc\" / wasm32 目标时才需要 Emscripten SDK。$(dependency_hint emcc)"
    fi
}

mobile_status() {
    echo "Android: $(dependency_hint android)"
    echo "iOS: $(dependency_hint ios)"
}

register_profile_file() {
    profile_file=$1
    mkdir -p "$(dirname "$profile_file")"
    touch "$profile_file"
    if ! grep -F "$PROFILE_SNIPPET" "$profile_file" >/dev/null 2>&1; then
        {
            echo ""
            echo "# EzLang"
            echo "[ -f \"$PROFILE_SNIPPET\" ] && . \"$PROFILE_SNIPPET\""
        } >> "$profile_file"
    fi
    if [ -z "${PROFILE_STATUS:-}" ]; then
        PROFILE_STATUS="$profile_file"
    else
        PROFILE_STATUS="$PROFILE_STATUS, $profile_file"
    fi
}

register_shell_profiles() {
    mkdir -p "$PREFIX"
    cat > "$PROFILE_SNIPPET" <<EOF
# EzLang
export EZLANG_HOME="$PREFIX"
case ":\$PATH:" in
  *":\$EZLANG_HOME/bin:"*) ;;
  *) export PATH="\$EZLANG_HOME/bin:\$PATH" ;;
esac
EOF

    PROFILE_STATUS=""
    if [ -n "${EZLANG_PROFILE:-}" ]; then
        register_profile_file "$EZLANG_PROFILE"
    else
        register_profile_file "$HOME/.zshrc"
        register_profile_file "$HOME/.zprofile"
        register_profile_file "$HOME/.bashrc"
        register_profile_file "$HOME/.bash_profile"
        register_profile_file "$HOME/.profile"
    fi
    PATH_STATUS="已写入 $PROFILE_SNIPPET，并注册到 $PROFILE_STATUS"
}

require_python
require_native_linker

if [ "$USE_LOCAL" = "1" ]; then
    SRC_DIR="$SCRIPT_DIR"
else
    require_git
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
    register_shell_profiles
else
    PATH_STATUS="已跳过 PATH 注册"
fi

echo "EzLang 已安装到 $PREFIX"
echo "源码目录: $SRC_DIR"
echo "安装校验: ez --version、ez install 与 ez build 通过"
echo "PATH 注册: $PATH_STATUS"
echo "EZLANG_HOME: $PREFIX"
echo "Python: $PYTHON_VERSION"
echo "LLVM: 使用 Python 包 llvmlite 提供的 LLVM binding，无需单独安装系统 LLVM"
echo "Emscripten: $(emcc_status)"
mobile_status
echo "当前 shell 临时启用: export EZLANG_HOME=\"$PREFIX\"; export PATH=\"$BIN_DIR:\$PATH\""
