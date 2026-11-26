# Avron plan

Private working repo for the @AvronMoneytalks X poster.

- `avron-x-merger/` holds the queue (`queue.jsonl`), the radar list (`radar.jsonl`), the posted log (`posted.jsonl`) and the writer script.
- `poster/` holds the posting scripts. They read the X keys from environment variables only. No keys are stored in this repo.

Keep this repo private: `queue.jsonl` has a private `verify_link` field per item that must never be posted.
