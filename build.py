from ezlang.compiler import EzLangCompiler

def main():
    compiler = EzLangCompiler()
    try:
        compiler.build_project()
    except Exception as e:
        print(f"Build failed: {e}")

if __name__ == "__main__":
    main()
