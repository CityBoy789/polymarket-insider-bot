
# Project Rules & Hard Constraints

## 1. Zero Tolerance for Fictive APIs
*   **Context**: The codebase must only use real, documented APIs.
*   **Rule**: Never assume an API endpoint exists. Verify it against official documentation (Polymarket CLOB API, Gamma API) or by testing.
*   **Enforcement**: Use `health_check.py` or unit tests to validate connectivity before deploying. If an API returns 404 or 401 unexpectedly, halt and fix the integration immediately. Do not "hallucinate" endpoints.

## 2. Mandatory Testing
*   **Context**: Code must be runnable and verified.
*   **Rule**: All new features must include a verification step (e.g., a test script like `backtest.py` or `test_startup.py`).
*   **Constraint**: Before adding a new feature, run the relevant test script. If it fails, do not proceed until fixed.

## 3. Strict Authentication Handling
*   **Context**: APIs often require signatures or keys.
*   **Rule**: If an API requires authentication (e.g., CLOB private endpoints), strictly implement the required headers (Timestamp, Signature, Key). Do not attempt to access private data without them.
*   **Action**: If `401 Unauthorized` occurs, check credentials and signing logic first.

## 4. Configuration validation
*   **Context**: Environment variables are critical.
*   **Rule**: Validate all required `.env` variables at startup. If critical keys (API Keys, Private Keys) are missing or invalid format, fail fast with a clear error message.
