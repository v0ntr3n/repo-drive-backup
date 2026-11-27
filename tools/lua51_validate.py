"""Parse Lua files without printing paths or compiler diagnostics."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def validate(root, compiler):
    passed = failed = 0
    def walk_error(_):
        raise RuntimeError("Source traversal failed")
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            if not name.endswith(".lua"):
                continue
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file():
                failed += 1
                continue
            try:
                result = subprocess.run(
                    [compiler, "-p", "--", str(path.absolute())],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=30, check=False,
                )
                if result.returncode == 0:
                    passed += 1
                else:
                    failed += 1
            except (OSError, subprocess.TimeoutExpired):
                failed += 1
    return passed, failed


def self_test(compiler):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "valid.lua").write_text("return 1\n")
        (root / "invalid.lua").write_text("local =\n")
        (root / "lua52-only.lua").write_text("goto label\n::label::\n")
        (root / "ignored.txt").write_text("local =\n")
        (root / "nested").mkdir()
        (root / "nested" / "space name.lua").write_text("return true\n")
        assert validate(root, compiler) == (2, 2)
        (root / "invalid.lua").unlink()
        (root / "lua52-only.lua").unlink()
        assert validate(root, compiler) == (2, 0)
    print("Validator self-test passed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    compiler = shutil.which("luac5.1")
    if not compiler:
        parser.exit(1, "Lua 5.1 compiler unavailable.\n")
    if args.self_test:
        self_test(compiler)
        return 0
    if args.root is None or not args.root.is_dir():
        parser.exit(1, "Source directory unavailable.\n")
    passed, failed = validate(args.root, compiler)
    print(f"Lua 5.1 syntax: {passed + failed} files; {passed} passed; {failed} failed.")
    if not passed and not failed:
        print("No Lua files found.")
        return 1
    return int(failed != 0)


if __name__ == "__main__":
    raise SystemExit(main())
