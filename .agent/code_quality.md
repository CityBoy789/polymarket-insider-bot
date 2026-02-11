# Code Quality Hard Constraints

> [!IMPORTANT]
> This file establishes the HARD constraints for code quality, formatting, and project structure as requested by the user.
> **All new code, refactoring, and future agent interactions MUST strictly adhere to these rules.**
> **Scope**: Project-wide.
> **Enforcement**: New conversations must determine/verify compliance.

## 1. Quality & Linting (Ruff)
- **Constraint**: Code must be compliant with the project's `pyproject.toml` configuration.
- **Command**: Run `ruff check .` to verify linting and `ruff format .` to apply formatting.
- **Rules**:
  - Max line length: **100** characters.
  - Quote style: **Double** quotes (`"`).
  - Indentation: **4 spaces**.
  - Imports: Must be sorted (isort rules via `ruff`).
  - No unused imports (`F401`) except in `__init__.py`.
  - Python Version: Target **Python 3.10+**.

## 2. Type Hinting (Python 3.10+)
- **Requirement**: **ALL** new functions and methods must have type annotations.
- **Syntax**: Use modern union syntax (`TypeA | TypeB`) where applicable.
- **Exceptions**: `self`, `cls` (usually inferred), but simple return types like `-> None` are mandatory.
- **Example**:
  ```python
  from typing import Any

  def process_data(items: list[str], options: dict[str, Any] | None = None) -> bool:
      ...
  ```

## 3. Asynchronous Code
- **Context**: The project relies on `asyncio` for high-performance trading.
- **Rule**:
  - Use `async`/`await` for all I/O operations (DB, Network).
  - **Forbidden**: Blocking calls inside async functions (e.g., `time.sleep()`, `requests.get()`).
  - **Required**: Use `asyncio.sleep()`, `aiohttp`, `aiosqlite` etc.

## 4. Documentation & Comments
- **Docstrings**: Public functions/classes must have a docstring describing:
  - Purpose
  - Arguments (name and type/description)
  - Return value
  - Exceptions raised
- **Style**: Google or NumPy style is accepted, be consistent.
- **Comments**: Explain *why*, not *what*, especially for complex trading logic.

## 5. Environment & Security
- **Rule**: NEVER hardcode API keys, private keys, or secrets.
- **Implementation**: Strict usage of `os.getenv()` or `config.py` loading from `.env`.
- **Validation**: Ensure `config.py` validates existence of keys at startup.

## 6. Testing Verification
- **Process**: New features are NOT complete until verified.
- **Requirement**: Create or update a verification script (e.g., `tests/` or `src/verify_...py`) and **RUN IT**.
- **Constraint**: Do not simply write code and assume it works. Proof of work (logs/output) is required.
