# Fantasy Portfolio Analysis

Analysis tools for fantasy portfolios.

## Requirements

- [Rye >= 0.43](https://rye.astral.sh)

## Installation

```sh
$ rye fetch
$ rye sync
```

## Usage

Put local (untracked) files and notebooks in ./local/

## Development

Install precommit hooks: `./install-hooks.sh`

Add dependencies: `rye add ...`

Run python files: `rye run python src/file.py`

Check precommit hooks: `rye run precommit`

Fix linting/formatting: `rye run fix`

Run tests: `rye test`

Resync dependencies/python version if changed: `rye sync`
