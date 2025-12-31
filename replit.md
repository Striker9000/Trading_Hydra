# Trading Hydra MVP

## Overview

A pure Python automated trading system that runs as a long-running process with multiple execution bots (MomentumBot, OptionsBot, CryptoBot). Uses Alpaca API for paper/live trading with fail-closed safety via ExitBot and dynamic budget allocation via PortfolioBot.

## Current State

- **Status**: Fully operational
- **Entry Point**: `python -m src.runner.main`
- **Loop Interval**: 5 seconds (configurable via settings.yaml)
- **Credentials**: Connected to Alpaca paper trading

## Project Architecture

### Directory Structure

```
config/
  settings.yaml       # System settings (timezone, loop interval, risk limits)
  bots.yaml          # Bot configurations (enable/disable, tickers, exit rules)

src/
  __init__.py
  runner/
    __init__.py
    main.py           # Long-running process entry point
  trading_hydra/
    __init__.py
    orchestrator.py   # 5-step trading loop orchestration
    core/
      __init__.py
      config.py       # YAML config loader
      state.py        # SQLite-backed state persistence
      logging.py      # JSONL file logger
      clock.py        # Market clock with timezone support
      risk.py         # Risk calculation utilities
      health.py       # Health monitoring
      halt.py         # Trading halt management
    services/
      __init__.py
      alpaca_client.py  # Alpaca API integration
      exitbot.py        # Kill-switch and safety checks
      portfolio.py      # Budget allocation
      execution.py      # Bot execution service
    bots/
      __init__.py
    utils/
      __init__.py

logs/
  app.jsonl           # Structured JSONL logs

state/
  trading_state.db    # SQLite state persistence
```

### Trading Loop (5 Steps)

1. **Initialize**: Fetch account equity from Alpaca, set day start reference
2. **ExitBot**: Check health and max daily loss - halt if violated
3. **PortfolioBot**: Allocate risk budgets to each execution bot
4. **Execution**: Run preflight checks, manage positions, look for entries
5. **Finalize**: Log summary, prepare for next iteration

### Key Features

- **Pure Python**: No TypeScript, Node, or external automation frameworks
- **Fail-Closed Safety**: System halts trading on any failure
- **Durable State**: SQLite-backed state survives restarts
- **Structured Logging**: JSONL format for easy parsing
- **Config-Driven**: YAML-based configuration for all parameters
- **Graceful Shutdown**: Handles SIGINT/SIGTERM signals

## Running the System

```bash
python -m src.runner.main
```

## Environment Variables

- `ALPACA_KEY`: Alpaca API key (required)
- `ALPACA_SECRET`: Alpaca API secret (required)
- `ALPACA_PAPER`: Set to "true" for paper trading (default: true)

## Configuration

### settings.yaml

- `runner.loop_interval_seconds`: Loop interval (default: 5)
- `system.timezone`: Market timezone (default: America/Los_Angeles)
- `risk.global_max_daily_loss_pct`: Max daily loss percentage (default: 1.0)
- `health.max_api_failures_in_window`: API failures before halt (default: 5)

### bots.yaml

Configure MomentumBot, OptionsBot, CryptoBot with tickers, risk limits, and enable/disable flags.

## Recent Changes

- 2024-12-30: Complete rebuild as pure Python
  - Removed all TypeScript/Node/Mastra dependencies
  - Created SQLite state persistence at ./state/trading_state.db
  - Created JSONL logging at ./logs/app.jsonl
  - Implemented 5-second config-driven loop
  - Implemented fail-closed safety with ExitBot/HaltManager
  - Added graceful shutdown signal handling
  - Verified working with Alpaca paper trading

## User Preferences

- Pure Python only (no TypeScript/Node)
- SQLite for local state persistence
- JSONL for structured logging
- Config-driven loop interval (not cron)
- Paper trading by default for safety
