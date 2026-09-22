# W73 Canonical Observation Contract v1

The canonical observation layer maps only fields explicitly present in the approved
Daywise XLSX source.

It does NOT:
- infer missing values;
- replace missing with zero/False;
- recreate V8 semantics;
- combine future intervals;
- modify the external source.

The raw source row is retained in the point-in-time cache. V8 feature derivation
remains a separate, frozen layer.
