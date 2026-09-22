# W73 Timestamp Contract

1. Preserve exact report timestamp from filename.
2. Never round source timestamps for storage.
3. Folder trading date is authoritative.
4. A point-in-time query may use only observations with timestamp <= cutoff.
5. Store source filename with every observation.
6. Keep data timestamp distinct from processing/display/alert timestamps.
7. Universe eligibility and priority decisions carry the exact observation timestamp.
8. Replay must reproduce the same point-in-time state from the cache.
