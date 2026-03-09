# Repo setup

We're going to setup our repo for python development.
We want a folder called `prism` to contain our main modules and code.
Package management should be with `uv`, and we want `ruff` with pre-commit for delinting.
We'll want to use pytest for tests. 
Set up a 'dev' esxtra dependencies group and add pytest and precommit to our extra dependencies.
Add developer setup instructions to our @README.md.

Plan before executing and ask for any feedback or clarification, appending it to this document.
When your're done executing, update the @CLAUDE.md with anything you've learned.

## Clarifications

- Python version: 3.13
- Ruff line length: 100 characters
- Ruff rules: E, F, I (pycodestyle errors, pyflakes, isort)
- Pre-commit hooks: ruff-check + ruff-format only
- venv: create with `uv venv --python 3.13` before running `uv sync`

## Status: DONE