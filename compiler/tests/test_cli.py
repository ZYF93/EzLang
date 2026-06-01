"""ez CLI 工具链测试"""

import os
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "compiler" / "src"))

from cli import ez


def write_project(
    tmp_path: Path,
    *,
    os_name: str = "linux",
    arch: str = "x86_64",
    public: bool = True,
    optimize: int = 0,
):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.ez").write_text("let x: I32 = 42;\n", encoding="utf-8")
    public_text = "true" if public else "false"
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        f"""
[project]
name = "demo"
version = "0.1.0"
main = "src/index.ez"
optimize = {optimize}
public = {public_text}
registry = "local"

[[output]]
arch = "{arch}"
os = "{os_name}"
dir = "dist/{os_name}"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return project_toml


def test_help_and_version(capsys):
    assert ez.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "usage:" in out
    assert "build" in out

    assert ez.main(["--version"]) == 0
    out = capsys.readouterr().out
    assert "ezlang 0.1.0" in out


def test_unknown_command_returns_error(capsys):
    assert ez.main(["missing"]) == 2
    err = capsys.readouterr().err
    assert "invalid choice" in err


@pytest.mark.parametrize("command", ["build", "run", "install", "fmt", "release"])
def test_subcommand_help(command, capsys):
    assert ez.main([command, "--help"]) == 0
    out = capsys.readouterr().out
    assert command in out


def test_build_writes_ir_for_output(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    ir_file = tmp_path / "dist" / "linux" / "demo.ll"
    assert "built linux/x86_64" in out
    assert ir_file.exists()
    assert 'ModuleID = "demo"' in ir_file.read_text(encoding="utf-8")


def test_build_writes_object_for_native_output(tmp_path, capsys):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
        optimize=2,
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    obj_file = tmp_path / "dist" / ez._native_os() / "demo.o"
    assert "object:" in out
    assert obj_file.exists()
    assert obj_file.stat().st_size > 0


def test_build_emits_objects_for_multiple_cross_targets(tmp_path, capsys):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.ez").write_text("const main = (): I32 => { return 0; };\n", encoding="utf-8")
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        """
[project]
name = "demo"
version = "0.1.0"
main = "src/index.ez"
optimize = 1

[[output]]
arch = "x86_64"
os = "linux"
dir = "dist/linux"

[[output]]
arch = "wasm32"
os = "emcc"
dir = "dist/web"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    linux_ir = (tmp_path / "dist" / "linux" / "demo.ll").read_text(encoding="utf-8")
    web_ir = (tmp_path / "dist" / "web" / "demo.ll").read_text(encoding="utf-8")
    assert "target triple = \"x86_64-unknown-linux-gnu\"" in linux_ir
    assert "target triple = \"wasm32-unknown-emscripten\"" in web_ir
    assert (tmp_path / "dist" / "linux" / "demo.o").exists()
    assert (tmp_path / "dist" / "web" / "demo.o").exists()
    assert "built linux/x86_64" in out
    assert "built emcc/wasm32" in out


def test_build_rejects_invalid_optimize(tmp_path, capsys):
    project_toml = write_project(tmp_path, optimize=4)

    assert ez.main(["build", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "project.optimize" in err


def test_build_accepts_wasm_arch_alias(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="emcc", arch="wasm")

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    captured = capsys.readouterr()
    assert "arch 'wasm' is deprecated" in captured.err
    assert (tmp_path / "dist" / "emcc" / "demo.ll").exists()


def test_build_discovers_import_dependency_graph(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    (tmp_path / "src" / "lib.ez").write_text("export let y: I32 = 1;\n", encoding="utf-8")
    (tmp_path / "src" / "index.ez").write_text(
        'from "./lib.ez" import { y };\nlet x: I32 = 42;\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    ir_text = (tmp_path / "dist" / "linux" / "demo.ll").read_text(encoding="utf-8")
    assert "sources: src/lib.ez, src/index.ez" in out
    assert '@"y"' in ir_text
    assert '@"x"' in ir_text


def test_build_loads_python_plugin_and_calls_hooks(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    plugin = tmp_path / "plugin.py"
    plugin.write_text(
        """
from pathlib import Path


def before_build(context):
    root = Path(context["root"])
    (root / "plugin-before.txt").write_text(
        "|".join([
            context["project"],
            context["output"]["os"],
            *context["args"],
            ",".join(Path(path).name for path in context["sources"]),
        ]),
        encoding="utf-8",
    )


def after_build(context):
    root = Path(context["root"])
    (root / "plugin-after.txt").write_text(
        "|".join([
            Path(context["ir"]).name,
            context["output"]["arch"],
        ]),
        encoding="utf-8",
    )
""".lstrip(),
        encoding="utf-8",
    )
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[[plugins]]\nname = "./plugin.py"\nargs = ["release=true", "backend=llvm"]\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 0

    captured = capsys.readouterr()
    assert "plugins are skipped" not in captured.err
    assert (tmp_path / "plugin-before.txt").read_text(encoding="utf-8") == "demo|linux|release=true|backend=llvm|index.ez"
    assert (tmp_path / "plugin-after.txt").read_text(encoding="utf-8") == "demo.ll|x86_64"


def test_build_rejects_invalid_plugin_args(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8")
        + '\n[[plugins]]\nname = "demo_plugin"\nargs = "release=true"\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "plugins.args" in err



def test_build_reports_missing_import(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="linux")
    (tmp_path / "src" / "index.ez").write_text(
        'from "./missing.ez" import { y };\nlet x: I32 = 42;\n',
        encoding="utf-8",
    )

    assert ez.main(["build", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "import 路径不存在" in err


def test_run_non_native_target_errors(tmp_path, capsys):
    project_toml = write_project(tmp_path, os_name="emcc", arch="wasm32")

    assert ez.main(["run", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "ez run only supports native target" in err


def test_run_native_executes_binary_and_returns_exit_code(tmp_path, capsys):
    project_toml = write_project(
        tmp_path,
        os_name=ez._native_os(),
        arch=ez._native_arch(),
    )
    (tmp_path / "src" / "index.ez").write_text(
        "const main = (): I32 => { return 7; };\n",
        encoding="utf-8",
    )

    assert ez.main(["run", "--project", str(project_toml)]) == 7

    captured = capsys.readouterr()
    assert 'ModuleID = "demo"' not in captured.out
    assert "native execution backend not implemented" not in captured.err
    assert (tmp_path / "dist" / ez._native_os() / "demo").exists()


def test_install_prints_validation_plan(tmp_path, capsys):
    (tmp_path / "local.ez").write_text("let x: I32 = 1;\n", encoding="utf-8")
    (tmp_path / "packages" / "lib").mkdir(parents=True)
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        """
[project]
name = "demo"
version = "0.1.0"

[deps]
local = "./local.ez"
workspace = "@workspace"

[workspace]
members = ["packages/*"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["install", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    assert "local local" in out
    assert "workspace workspace" in out



def test_install_downloads_remote_version_dependency(tmp_path, capsys):
    registry = tmp_path / "registry"
    package = registry / "remote" / "1.2.3"
    package.mkdir(parents=True)
    (package / "remote.ez").write_text("export let answer: I32 = 42;\n", encoding="utf-8")
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        f"""
[project]
name = "demo"
version = "0.1.0"
registry = "{registry}"

[deps]
remote = "1.2.3"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["install", "--project", str(project_toml)]) == 0

    out = capsys.readouterr().out
    installed = tmp_path / ".ez" / "deps" / "remote" / "1.2.3" / "remote.ez"
    assert installed.read_text(encoding="utf-8") == "export let answer: I32 = 42;\n"
    assert f"remote remote 1.2.3 {installed.parent}" in out



def test_install_remote_dependency_requires_registry(tmp_path, capsys):
    project_toml = tmp_path / "project.toml"
    project_toml.write_text(
        """
[project]
name = "demo"
version = "0.1.0"

[deps]
remote = "1.2.3"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert ez.main(["install", "--project", str(project_toml)]) == 1

    err = capsys.readouterr().err
    assert "registry" in err


def test_fmt_check_parses_ez_files(tmp_path, capsys):
    project_toml = write_project(tmp_path)
    source = tmp_path / "src" / "index.ez"

    assert ez.main(["fmt", "--project", str(project_toml), "--check", str(source)]) == 0

    out = capsys.readouterr().out
    assert "checked 1 file" in out



def test_fmt_rewrites_single_file(tmp_path, capsys):
    project_toml = write_project(tmp_path)
    source = tmp_path / "src" / "index.ez"
    source.write_text("let   x:I32=1;\nconst main=():I32=>{return x;}\n", encoding="utf-8")

    assert ez.main(["fmt", "--project", str(project_toml), str(source)]) == 0

    assert source.read_text(encoding="utf-8") == "let x: I32 = 1;\nconst main = (): I32 => {\n    return x;\n}\n"
    out = capsys.readouterr().out
    assert "formatted 1 file" in out



def test_fmt_formats_multiple_files_in_directory(tmp_path, capsys):
    project_toml = write_project(tmp_path)
    first = tmp_path / "src" / "a.ez"
    second = tmp_path / "src" / "b.ez"
    first.write_text("let   a:I32=1;\n", encoding="utf-8")
    second.write_text("let   b:I32=2;\n", encoding="utf-8")

    assert ez.main(["fmt", "--project", str(project_toml), str(tmp_path / "src")]) == 0

    assert first.read_text(encoding="utf-8") == "let a: I32 = 1;\n"
    assert second.read_text(encoding="utf-8") == "let b: I32 = 2;\n"
    out = capsys.readouterr().out
    assert "formatted 3 files" in out



def test_fmt_check_reports_unformatted_without_rewriting(tmp_path, capsys):
    project_toml = write_project(tmp_path)
    source = tmp_path / "src" / "index.ez"
    original = "let   x:I32=1;\n"
    source.write_text(original, encoding="utf-8")

    assert ez.main(["fmt", "--project", str(project_toml), "--check", str(source)]) == 1

    assert source.read_text(encoding="utf-8") == original
    err = capsys.readouterr().err
    assert "需要格式化" in err


def test_release_dry_run_validates_metadata(tmp_path, capsys):
    project_toml = write_project(tmp_path)

    assert ez.main(["release", "--project", str(project_toml), "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "release dry-run demo 0.1.0" in out


def test_release_packs_and_publishes_to_local_registry(tmp_path, capsys):
    registry = tmp_path / "registry"
    project_toml = write_project(tmp_path)
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('registry = "local"', f'registry = "{registry}"'),
        encoding="utf-8",
    )
    (tmp_path / "README.tmp").write_text("ignored\n", encoding="utf-8")

    assert ez.main(["release", "--project", str(project_toml)]) == 0

    package = registry / "demo" / "0.1.0" / "demo-0.1.0.zip"
    assert package.exists()
    with zipfile.ZipFile(package) as archive:
        assert sorted(archive.namelist()) == ["project.toml", "src/index.ez"]
        assert archive.read("src/index.ez").decode() == "let x: I32 = 42;\n"
    out = capsys.readouterr().out
    assert f"released demo 0.1.0 {package}" in out



def test_release_posts_package_to_http_registry(tmp_path, monkeypatch, capsys):
    project_toml = write_project(tmp_path)
    project_toml.write_text(
        project_toml.read_text(encoding="utf-8").replace('registry = "local"', 'registry = "https://registry.example"'),
        encoding="utf-8",
    )
    captured = {}

    def fake_urlopen(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["content_type"] = request.headers["Content-type"]
        captured["data"] = request.data

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"ok"

        return Response()

    monkeypatch.setattr(ez.urllib.request, "urlopen", fake_urlopen)

    assert ez.main(["release", "--project", str(project_toml)]) == 0

    assert captured["url"] == "https://registry.example/demo/0.1.0/demo-0.1.0.zip"
    assert captured["method"] == "PUT"
    assert captured["content_type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(captured["data"])) as archive:
        assert "project.toml" in archive.namelist()
        assert "src/index.ez" in archive.namelist()
    out = capsys.readouterr().out
    assert "released demo 0.1.0 https://registry.example/demo/0.1.0/demo-0.1.0.zip" in out



def test_release_rejects_private_package(tmp_path, capsys):
    project_toml = write_project(tmp_path, public=False)

    assert ez.main(["release", "--project", str(project_toml), "--dry-run"]) == 1

    err = capsys.readouterr().err
    assert "public = false" in err
