-- Restrict proprietary data tables from anonymous access.
-- Before: anon key could read scores, features, labels, holders, pools.
-- After: only authenticated users (or service_role) can read them.
-- Dashboard uses service_role → unaffected.
-- Landing API uses service_role server-side → unaffected.

-- 1. SCORES (gem probabilities, signals — paid product)
DROP POLICY IF EXISTS "Anyone can read scores" ON scores;
CREATE POLICY "Authenticated users read scores" ON scores
  FOR SELECT USING (auth.uid() IS NOT NULL OR current_setting('role') = 'service_role');

-- 2. FEATURES (94 ML features per token — core IP)
DROP POLICY IF EXISTS "anon_read_features" ON features;
CREATE POLICY "Authenticated users read features" ON features
  FOR SELECT USING (auth.uid() IS NOT NULL OR current_setting('role') = 'service_role');

-- 3. LABELS (gem/rug classifications — core IP)
DROP POLICY IF EXISTS "anon_read_labels" ON labels;
CREATE POLICY "Authenticated users read labels" ON labels
  FOR SELECT USING (auth.uid() IS NOT NULL OR current_setting('role') = 'service_role');

-- 4. HOLDER_SNAPSHOTS (wallet concentration data)
DROP POLICY IF EXISTS "anon_read_holder_snapshots" ON holder_snapshots;
CREATE POLICY "Authenticated users read holder_snapshots" ON holder_snapshots
  FOR SELECT USING (auth.uid() IS NOT NULL OR current_setting('role') = 'service_role');

-- 5. POOL_SNAPSHOTS (liquidity, volume, buyer/seller data)
DROP POLICY IF EXISTS "anon_read_pool_snapshots" ON pool_snapshots;
CREATE POLICY "Authenticated users read pool_snapshots" ON pool_snapshots
  FOR SELECT USING (auth.uid() IS NOT NULL OR current_setting('role') = 'service_role');

-- Tables that REMAIN public (commodity data):
-- tokens, ohlcv, contract_info, model_versions, drift_reports
