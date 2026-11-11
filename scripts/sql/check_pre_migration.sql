-- Read-only checks before applying migration V3.1.
-- First query must yield ZERO rows; if not, stop and reconcile before migration.
SELECT meter_id, cutoff_at, COUNT(*) AS active_cutoff_count, array_agg(id) AS cutoff_ids
FROM meter_cutoffs WHERE status <> 'SUPERSEDED'
GROUP BY meter_id, cutoff_at HAVING COUNT(*) > 1;
