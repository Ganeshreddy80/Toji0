# TOJI Security Audit Report

## 1. Secrets Leakage

- **Hardcoded Secrets**: The `.env` template contains active/mock API credentials that are easily exposed.
  - `BINANCE_API_KEY`: Hardcoded.
  - `BINANCE_API_SECRET`: Hardcoded.
  - `OPENROUTER_API_KEY`: Hardcoded sk-or API key.
  - `TELEGRAM_BOT_TOKEN`: Hardcoded Telegram Token.
  - `TELEGRAM_CHAT_ID`: Hardcoded Telegram Chat ID.
- **Git Exposure**: The project is not initialized as a git repository (`fatal: not a git repository`), which increases the risk of accidentally committing `.env` if git is initialized without tracking ignores.

---

## 2. API & Authentication

- **Hardcoded API Keys in Main**:
  - `TOJI_ADMIN_API_KEY` is hardcoded as `toji_admin_secret_key_12345` in the config file.
  - `TOJI_ANALYST_API_KEY` is hardcoded as `toji_analyst_secret_key_67890` in the config file.
- **CORS Configuration**:
  - In `backend/main.py`, CORS is configured to allow all origins (`allow_origins=["*"]`).
  - **Risk**: Allows cross-origin requests from any website, leaving the trading dashboard vulnerable to Cross-Site Request Forgery (CSRF) and unauthorized access if API keys are leaked.

---

## 3. Logging Exposure

- **API Keys in Logs**: The system does not redact secret API keys or headers from `system.log` when requests fail or during connection handshakes.
- **Docker Exposure**: If docker logs are captured by third-party log aggregators, the hardcoded environment variables will be visible via inspection.
