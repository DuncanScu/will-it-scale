from pathlib import Path


def read_source_file(
    source_root: Path,
    relative_path: str,
    allowed_suffixes: frozenset[str],
) -> str:
    source_root = source_root.resolve()
    source_path = (source_root / relative_path).resolve()
    try:
        source_path.relative_to(source_root)
    except ValueError as error:
        raise ValueError("The requested file must be inside the application source directory") from error

    if source_path.suffix not in allowed_suffixes or not source_path.is_file():
        raise ValueError("The requested file must be an existing allowed source file")
    if source_path.stat().st_size > 100_000:
        raise ValueError("The requested file exceeds the 100 KB read limit")

    return source_path.read_text(encoding="utf-8")


def read_application_source_file(source_root: Path, relative_path: str) -> str:
    return read_source_file(source_root, relative_path, frozenset({".py"}))