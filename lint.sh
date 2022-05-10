#!/usr/bin/env bash

sep() {
  echo
  echo --------------------------------------------------------------------------------
  echo
}

poetry run isort .
sep
poetry run black .
sep
poetry check
sep
poetry run flake8 .
sep
poetry run pydocstyle .
sep
poetry run mypy .
sep
#poetry run pytest
