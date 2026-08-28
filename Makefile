.PHONY: test example wheel

test:
	PYTHONPATH=src pytest

example:
	cd examples/basic && PYTHONPATH=../../src python -m locus_md config validate && PYTHONPATH=../../src python -m locus_md lint && PYTHONPATH=../../src python -m locus_md verify --offline && PYTHONPATH=../../src python -m locus_md sync --check --offline

wheel:
	python -m pip wheel . --no-deps -w dist
