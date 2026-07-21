# Contributing to ProxyGuard

Thank you for your interest! Contributions, bug reports, and feature ideas are all welcome.

## Getting Started

```bash
# 1. Fork & clone
git clone https://github.com/AnnonumusC/ProxyGuard.git
cd proxyguard

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install core + optional dependencies
pip install -r requirements.txt
pip install -r requirements-optional.txt

# 4. Run from source
python proxy_guard.py --help
```

## Reporting Bugs

Please open a [GitHub Issue](https://github.com/AnnonumusC/ProxyGuard/issues) with:

- Python version (`python --version`)
- OS and version
- Full command you ran
- Full error output / traceback

## Pull Requests

1. Branch from `main`: `git checkout -b feat/my-feature`
2. Keep changes focused — one feature or fix per PR
3. Update `CHANGELOG.md` under an `[Unreleased]` heading
4. Test manually with a local proxy list before submitting
5. Open the PR against `main`

## Code Style

- Python 3.10+ syntax; type-annotated where it aids clarity
- `black` for formatting (not enforced by CI yet, but appreciated)
- No new hard dependencies — new optional features go behind a `try/except ImportError`

## Adding a New Feature

The project is a single-file script (`proxy_guard.py`) by design, so:
- Keep new classes/functions grouped near related code
- Mark optional imports with a `try/except` + a `_feature_available` flag
- Add the new dependency to `requirements-optional.txt` and `pyproject.toml [project.optional-dependencies]`

## License

By contributing you agree that your contributions will be licensed under the MIT License.
