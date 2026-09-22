# W73 Replay Contract v1

Replay is point-in-time.

For cutoff timestamp T, only interval files with:
`source_timestamp <= T`
are eligible.

Historical months such as `August26` and `july26` are valid when explicitly selected.

The replay engine does not use later intervals to construct an earlier point.
