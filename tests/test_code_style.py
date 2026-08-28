from pathlib import Path


def test_python_lines_do_not_exceed_200_characters() -> None:
    repository = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for root in (repository / "src", repository / "tests"):
        for path in root.rglob("*.py"):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if len(line) > 200:
                    offenders.append(f"{path.relative_to(repository)}:{line_number}:{len(line)}")
    assert offenders == []
