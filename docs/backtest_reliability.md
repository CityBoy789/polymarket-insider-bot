# Backtest Reliability Report

## Overview
This document details the methodologies used to ensure the reliability of backtesting in the Polymarket Insider Tracker. Our goal is to eliminate **Look-Ahead Bias** and **Overfitting**, providing a realistic estimate of live trading performance.

## 1. Look-Ahead Bias Elimination

### The Problem
Traditional backtests often use:
*   **Close Price** of the current bar for entry (impossible in real-time).
*   **High/Low** prices that might have occurred *after* the signal.
*   **Future Data** for indicator calculation.

### Our Solution (`src/fixes/realistic_backtest.py`)
We enforce strict causality:
*   **Entry**: Uses `RealisticTradingModel` which adds a `latency_seconds` delay (default 2s) after the signal timestamp.
*   **Price**: Can ONLY use data available *at or before* the execution timestamp.
*   **Exit**: Uses Time-Weighted Average Price (TWAP) +/- 30 minutes around the target exit time to simulate liquidity constraints.

## 2. Realistic Transaction Costs

We model the "Frictions" of real trading:

### Market Impact
Large orders move the price against you.
*   **Model**: We analyze the Order Book depth.
*   **Logic**: `Impact = |Avg_Exec_Price - Best_Price|`.
*   **Implementation**: `src/fixes/trading_reality.py`.

### Slippage & Spread
Even small orders pay the spread (difference between Buy and Sell price).
*   **Base Slippage**: 20 bps (0.2%) added to all trades to account for volatility.

### Fees
*   **Polymarket Fee**: ~0.1% (or current rate) per transaction.

## 3. Overfitting Prevention

### Walk-Forward / K-Fold Cross Validation
We do NOT optimize parameters on the entire dataset.
*   **Method**: 5-Fold Cross Validation.
*   **Split**: Data is split into Training (70%) and Testing (30%) sets.
*   **Rule**: We report performance primarily on the **Test Set** (Out-of-Sample).

If `Train Score >> Test Score`, the model is **Overfit** and rejected.

## 4. Verification Steps

Before enabling live trading:
1.  Run `python tests/test_end_to_end.py` to verify the pipeline.
2.  Enable `SIMULATION_MODE=true` in `.env`.
3.  Let the bot run for 30 days.
4.  Compare `simulation` PnL vs `backtest` PnL. Deviation should be < 20%.

## Conclusion
A "bad" backtest result that is **realistic** is infinitely better than a "great" backtest result that is **fake**. We prioritize honesty over hype.
