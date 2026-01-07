
---

```md
# Trading_Hydra

**Trading_Hydra** is a fail-closed, stateful trading system designed to run continuously against a single Alpaca account (paper first), execute multiple strategy bots per loop, and **refuse to trade unless the system is healthy**.

This repository is intentionally built as a **production-style scaffold**: execution, risk, logging, and persistence are real; trading “edge” logic is intentionally minimal and pluggable.

The goal is **reliability first … strategy second**.

---

## What This Project Does

At runtime, Trading_Hydra:

- Boots a controlled execution loop  
- Performs pre-flight health checks every cycle  
- Loads configuration-defined bots (Momentum, Options, Crypto)  
- Evaluates risk and account constraints  
- Executes trades **only if all safety gates pass**  
- Logs every decision and persists state durably  
- Halts trading immediately if anything critical breaks  

If something fails … **trading stops**.  
No retries. No silent degradation. No “hope mode”.

---

## Core Design Goals (from MVP Notes)

These are not aspirational … they are implemented or explicitly scaffolded:

- Run on **one Alpaca account** (paper trading first)  
- **Fail closed** on errors or unhealthy state  
- Log everything in **structured JSONL**  
- Persist runtime state using **SQLite**  
- Run all bots every loop, gated behind preflight checks  
- Support **multiple MomentumBots per ticker** via config  
- Include **OptionsBot** and **CryptoBot** as first-class citizens  
- Keep strategy “edge” logic **thin and replaceable**  

This repo is **the engine**, not the secret sauce.
```



````
---

## Repository Structure (1:1 Mapping)

```

Trading_Hydra-main/
├── attached_assets/
│   └── MVP system goals and design notes
│
├── src/
│   └── trading_hydra/
│       ├── bots/
│       │   ├── momentum_bot.py   # Momentum strategy bot
│       │   ├── options_bot.py    # Options execution scaffold
│       │   └── crypto_bot.py     # Crypto execution scaffold
│       │
│       ├── engine/
│       │   ├── execution.py      # Central execution loop
│       │   └── exitbot.py        # Position exit / unwind logic
│       │
│       ├── risk/
│       │   └── portfolio.py      # Portfolio + risk state tracking
│       │
│       ├── mock_data.py          # Mock/testing data
│       └── **init**.py
│
├── tests/
│   ├── qc_runner.py              # QC orchestration
│   ├── run_qc.py                 # Test entrypoint
│   └── bot_stress_test.py        # Stress testing logic
│
├── utils/
│   └── **init**.py
│
├── state/
│   └── trading_state.db          # SQLite persistent state
│
├── logs/                         # Runtime JSONL logs (generated)
│
├── main.py                       # System entrypoint
├── run_qc_tests.py               # Fast preflight checks
├── run_comprehensive_qc.py       # Full system validation
├── test_alpaca_connection.py     # Broker connectivity check
├── reconnect_alpaca.py           # Broker reconnection helper
├── verify_account_balance.py     # Account sanity verification
├── check_io.py                   # Filesystem / I/O validation
├── fix_system_errors.py          # Known error recovery helper
├── enable_dev_mode.py            # Non-destructive dev mode toggle
├── install_trading_hydra.sh      # Bootstrap installer
├── pyproject.toml                # Dependencies + project metadata
└── uv.lock                       # Locked dependency graph

````

---

## Execution Model

Trading_Hydra is **loop-driven**.  
Every loop iteration follows the same discipline:

### 1. System Health Validation
- Broker connectivity  
- Account access  
- State availability  
- I/O readiness  

### 2. Risk and Portfolio Checks
- Capital constraints  
- Position limits  
- Existing exposure  

### 3. Bot Evaluation
- MomentumBots (multiple per ticker allowed)  
- OptionsBot (scaffolded)  
- CryptoBot (scaffolded)  

### 4. Trade Execution
- Orders placed **only if all gates pass**

### 5. Persistence
- State written to SQLite  
- Decisions logged to JSONL  

If any step fails … **execution halts cleanly**.

---

## Bots (What Exists vs What’s Intentional)

### MomentumBot
- Fully wired into the execution loop  
- Designed to be instantiated multiple times per ticker  
- Strategy logic intentionally minimal and replaceable  

### OptionsBot
- Execution scaffold is real  
- Strategy logic intentionally placeholder  
- Designed to accept CSPs, spreads, or custom logic later  

### CryptoBot
- First-class citizen in the engine  
- Execution flow exists  
- Strategy logic intentionally thin  

This separation is deliberate.  
The system is built so **bad strategy code cannot crash the engine**.

---

## State, Logging, and Safety

### State
Stored in `state/trading_state.db` (SQLite).  
Survives restarts. No in-memory illusions.

### Logs
JSONL format.  
Every decision. Every failure. Every skip.

### Fail-Closed Behavior
No trade executes if:

- Broker is unreachable  
- Account data is invalid  
- State cannot be written  
- QC checks fail  

This is **not negotiable** in the design.

---

## Quality Control (QC)

Before running `main.py`, you’re expected to run QC:

```bash
python run_qc_tests.py
````

For deeper validation:

```bash
python run_comprehensive_qc.py
```

QC exists to answer one question:

> **“Is the system allowed to trade right now?”**

---

## Quick Start (Recommended Run Order)

### 1. Verify Environment + Broker Access

```bash
python check_io.py
python test_alpaca_connection.py
python verify_account_balance.py
```

### 2. Run QC Gates

```bash
python run_qc_tests.py
# or
python run_comprehensive_qc.py
```

### 3. Run the Engine

```bash
python main.py
```

---

## Recruiter / Reviewer Notes

If you’re evaluating engineering quality, start here:

* `src/trading_hydra/engine/execution.py` … loop orchestration + fail-closed control flow
* `src/trading_hydra/risk/portfolio.py` … risk model + state interaction
* `tests/qc_runner.py` … preflight gating and validation strategy
* `state/trading_state.db` … persisted runtime state (SQLite)
* `logs/` … structured JSONL audit trail output

---

## Disclaimer

This repository can place real trades depending on configuration.

* Start in paper mode
* Review all risk constraints
* You are responsible for compliance and financial outcomes

This project is **infrastructure**, not financial advice.

---

## Author

Built by **Striker9000**
Systems-first engineer applying production discipline to automated trading.

```

---

### Final blunt assessment

This README now:

- Reads like a **real system**, not a side project  
- Signals **defensive engineering + operational maturity**  
- Makes recruiters want to open `execution.py`, not close the tab  
- Matches the repo **exactly**, line for line  

If you want next upgrades, the only remaining high-leverage moves are:

- A single execution-flow diagram (PNG or ASCII)  
- Docstrings in `execution.py` and `portfolio.py`  
- One example config snippet for MomentumBot  

But as a GitHub front door … this is strong.
```
