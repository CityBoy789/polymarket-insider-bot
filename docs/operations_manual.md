# Operations Manual

## Routine Maintenance

### Daily
1.  **Check Logs**: Review `tracker.log` for errors or connection issues.
2.  **Monitor Dashboard**: Run `python src/fixes/monitoring_dashboard.py` (when integrated) or check database stats.
3.  **Verify Positions**: Ensure `SIMULATION_MODE` positions match expected strategy logic.

### Monthly
1.  **Parameter Re-Optimization**:
    *   Markets change. The optimal `FRESH_WALLET_DAYS` or `SCORE_THRESHOLD` in January might not work in February.
    *   **Action**: Run `python src/fixes/parameter_optimization.py`.
    *   **Apply**: Update `.env` with new "Best Parameters".
2.  **Backtest vs Live Review**:
    *   Calculate `Live ROI` / `Live Sharpe`.
    *   Compare with `Backtest` expectations.
    *   **Threshold**: If disparity > 20%, HALT trading and investigate.

### Quarterly
1.  **Codebase Update**: Pull latest changes.
2.  **Review Strategy**: Is the "Insider" thesis still valid? Are there new types of "Insiders" (e.g. influencers vs corporate)?

## Troubleshooting

### Issue: "Live ROI is much worse than Backtest"
*   **Cause 1**: Slippage is higher than modeled.
    *   *Fix*: Increase `slippage_bps` in `RealisticTradingModel` and re-backtest.
*   **Cause 2**: Market Impact.
    *   *Fix*: Your `MAX_BET_AMOUNT` might be too high for the liquidity. Reduce it.
*   **Cause 3**: Overfitting.
    *   *Fix*: Your parameters are too tuned to history. Relax constraints (e.g. lower threshold, lower win rate req).

### Issue: "No Trades are being taken"
*   **Cause**: Strict parameters.
*   *Check*: `min_market_liquidity` might be too high for current market conditions.
*   *Check*: `score_threshold` (e.g. 9.0) might be too rare.

## Safety First
*   **Kill Switch**: Set `COPY_TRADING_ENABLED=false` in `.env` immediately if behavior is erratic.
*   **Loss Limits**: Respect `DAILY_LOSS_LIMIT`. Do not manually override it "just this once".
