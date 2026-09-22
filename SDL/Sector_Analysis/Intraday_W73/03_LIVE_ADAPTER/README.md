# Read-only live adapter

This is the ONLY external runtime boundary.

It may READ the existing live intraday pipeline and transform data into W73-owned
point-in-time snapshots.

It must never import old analysis modules or write to the source pipeline.
