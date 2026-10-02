from pathlib import Path

ROOT = Path("./src")
OUTPUT = Path("project_code.md")


def main():
    py_files = sorted(path for path in ROOT.rglob("*.py") if path.resolve() != OUTPUT.resolve())

    with OUTPUT.open("w", encoding="utf-8") as md:
        for path in py_files:
            relative_path = path.relative_to(ROOT)

            md.write(f"## `{relative_path}`\n\n")
            md.write(f"**Path:** `{path.resolve()}`\n\n")
            md.write("```python\n")

            try:
                md.write(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                md.write("# Не удалось прочитать файл как UTF-8\n")

            md.write("\n```\n\n")

    print(f"Собрано файлов: {len(py_files)}")
    print(f"Результат: {OUTPUT.resolve()}")


if __name__ == "__main__":
    main()
