# Systematic detector design
User delegates product and implementation decisions. Preserve the existing Next.js dashboard, navigation, cards, coin list and Detection Lab. Run on UI 3000 and FastAPI 8000.

Use five-minute completed candles, a two-hour feature window, and a fifteen-minute forecast target. Scan every 60 seconds without overlapping scans. Coinbase is primary (Binance is geo-blocked here); CoinGecko supplies metadata, not fabricated minute candles. Cointelegraph RSS supplies timestamped headline sentiment via a disclosed lexicon. Missing news is explicitly represented. Missing/stale price data yields unavailable, never clear.

Train a multiclass logistic model with NumPy on recorded real candles and weak labels for future abnormal price movement; these labels are not proof of manipulation. Split chronologically with purged windows. Save data hashes, code versions, parameters, metrics and artifacts in SQLite/on disk. Run 32 experiments and promote by validation score, reporting held-out results and label limitations. No fabricated metrics or silent synthetic market fallback.

C++ computes market features, learned softmax scoring, and replay of recorded feature windows with an atomic work index and std::thread workers. Compare actual one-worker and multi-worker times and score checksums. The requested 12-to-4-minute claim remains an unverified historical target unless measurements establish it.

Alternatives considered: keep heuristics (does not satisfy ML); external job stack and paid feeds (unnecessary local dependencies); durable SQLite plus bounded workers (chosen for reproducible local operation). Remove legacy remote database writes and embedded credentials from deliverable. No trading actions.
