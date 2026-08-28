.PHONY: test example wheel install-tool

test:
	PYTHONPATH=src pytest

example:
	cd examples/basic && locus.md config validate && locus.md lint && locus.md verify --offline && locus.md sync --check --offline

wheel:
	python -m pip wheel . --no-deps -w dist

install-tool:
	uv tool install --force .
