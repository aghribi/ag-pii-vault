.PHONY: install spacy test lint fmt

install:
	pip install -e ".[all]"

spacy:
	python -m spacy download en_core_web_lg

test:
	pytest tests/ -v

lint:
	ruff check ag_pii_vault/

fmt:
	black ag_pii_vault/ tests/
