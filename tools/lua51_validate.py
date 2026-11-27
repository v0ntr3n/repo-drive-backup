"""Parse Lua files; optionally report failed paths and line numbers only."""
import argparse
import os
from pathlib import Path
import shutil
import json
import re
import io
from contextlib import redirect_stdout
import subprocess
import tempfile


def validate(root, compiler, show_failed_paths=False):
    def report(path, line=None):
        if show_failed_paths:
            # JSON encoding prevents control characters in paths from becoming
            # terminal escapes or GitHub Actions workflow commands.
            relative = json.dumps(path.relative_to(root).as_posix(), ensure_ascii=True)
            print(f"FAIL {relative}" + (f":{line}" if line is not None else ""))
    passed = failed = 0
    def walk_error(_):
        raise RuntimeError("Source traversal failed")
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(files):
            if not name.endswith(".lua"):
                continue
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file():
                failed += 1
                report(path)
                continue
            try:
                result = subprocess.run(
                    [compiler, "-p", "--", str(path.absolute())],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE if show_failed_paths else subprocess.DEVNULL,
                    timeout=30, check=False,
                )
                if result.returncode == 0:
                    passed += 1
                else:
                    failed += 1
                    line = None
                    if show_failed_paths:
                        # Match the exact compiler input path, never echo stderr.
                        marker = os.fsencode(str(path.absolute()))
                        match = re.search(rb"(?m)^.*?" + re.escape(marker) + rb":([0-9]{1,9}):", result.stderr)
                        if match:
                            line = int(match.group(1))
                    report(path, line)
            except (OSError, subprocess.TimeoutExpired):
                failed += 1
                report(path)
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
        with redirect_stdout(io.StringIO()) as hidden:
            assert validate(root, compiler) == (2, 2)
        assert hidden.getvalue() == ""
        with redirect_stdout(io.StringIO()) as visible:
            assert validate(root, compiler, show_failed_paths=True) == (2, 2)
        lines = visible.getvalue().splitlines()
        assert lines == ['FAIL "invalid.lua":1', 'FAIL "lua52-only.lua":1'], lines
        (root / "invalid.lua").unlink()
        (root / "lua52-only.lua").unlink()
        assert validate(root, compiler) == (2, 0)
    print("Validator self-test passed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--show-failed-paths", action="store_true",
                        help="Print failed relative paths and line numbers (public CI logs)")
    args = parser.parse_args()
    compiler = shutil.which("luac5.1")
    if not compiler:
        parser.exit(1, "Lua 5.1 compiler unavailable.\n")
    if args.self_test:
        self_test(compiler)
        return 0
    if args.root is None or not args.root.is_dir():
        parser.exit(1, "Source directory unavailable.\n")
    passed, failed = validate(args.root, compiler, args.show_failed_paths)
    print(f"Lua 5.1 syntax: {passed + failed} files; {passed} passed; {failed} failed.")
    if not passed and not failed:
        print("No Lua files found.")
        return 1
    return int(failed != 0)


if __name__ == "__main__":
    raise SystemExit(main())
