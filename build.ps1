# Сборка standalone-версии через Nuitka. Результат: compiled/main.dist/VRMonitor.exe
uv sync --dev
uv run python -m nuitka `
    --standalone `
    --assume-yes-for-downloads `
    --msvc=latest `
    --enable-plugin=pyside6 `
    --user-package-configuration-file=nuitka-package.config.yml `
    --include-package=comtypes `
    --include-data-dir=src/static=static `
    --windows-console-mode=attach `
    --output-filename=VRMonitor.exe `
    --output-dir=compiled `
    src/main.py
