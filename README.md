# Python Rye Template

## Requirements

- [Rye >= 0.43](https://rye.astral.sh)

You may need to load rye in your .bash_profile or similar:

```sh
echo '. ~/.rye/env' >> ~/.bash_profile
. ~/.bash_profile
```

## Installation

```sh
$ rye fetch
$ rye sync
$ ./install_hooks.sh
```

## Usage

Put local (untracked) files and notebooks in ./local/

Add dependencies: `rye add ...`

Run python files: `rye run python src/file.py`

Check precommit hooks: `rye run precommit`

Fix linting/formatting: `rye run fix`

Run tests: `rye test`

Resync dependencies/python version if changed: `rye sync`
