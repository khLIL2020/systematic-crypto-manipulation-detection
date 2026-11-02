# Domain vocabulary
- Market observation: completed five-minute Coinbase candle with original timestamp and volume.
- Feature window: 25 aligned observations yielding 24 returns (two hours), paired with BTC and preceding 24-hour dated headline sentiment.
- Weak anomaly label: unusual future 15-minute absolute price direction and BTC-relative return; not verified manipulation.
- Risk score: 1 minus the normal-class softmax score; uncalibrated and experimental.
- Directional alert: possible pump or dump when the corresponding class score reaches 0.65. Watch begins at combined anomaly score 0.5.
- Unavailable: no trained model, insufficient/gapped candles, failed feed, or observations older than ten minutes. Never synonymous with clear.
- Experiment: persistent configuration plus dataset, source and binary identities, execution status, measured metrics and optional artifact.
- Promotion: select a trained model for subsequent scans and evaluate its held-out partition.
- Replay: repeated scoring of recorded feature windows; does not simulate exchange fills, order books or P&L.
