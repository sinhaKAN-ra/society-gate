"""Export this standalone application without credentials, caches, or local state."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
target = root / ".local" / "exports" / "society-gate-source.zip"
target.parent.mkdir(parents=True, exist_ok=True)
excluded = {".local", ".venv", "venv", "__pycache__", ".pytest_cache", ".git", ".DS_Store", "build", "dist"}
with ZipFile(target, "w", ZIP_DEFLATED) as archive:
    for file in sorted(root.rglob("*")):
        relative = file.relative_to(root)
        if file.is_file() and not file.is_symlink() and not any(part in excluded or part.endswith(".egg-info") for part in relative.parts) and file.suffix not in (".pyc", ".pyo"):
            archive.write(file, Path("society-gate") / relative)
print(target)
