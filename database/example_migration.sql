-- ============================================================================
-- Example Migration Script
-- ============================================================================
-- Purpose: Demonstrates safe schema evolution for financial audit compliance
-- Scenario: Adding minimum trading days requirement to challenges
-- ============================================================================

-- ============================================================================
-- MIGRATION METADATA
-- ============================================================================

-- Migration: 001_add_min_trading_days
-- Author: Database Engineering Team
-- Date: 2024-01-19
-- Description: Add minimum_trading_days field to challenges table
-- Impact: Low - backward compatible, no data loss
-- Rollback: Supported (see rollback section)

-- ============================================================================
-- PRE-MIGRATION VALIDATION
-- ============================================================================

-- Verify current schema version
DO $$
BEGIN
    -- Check if column already exists
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'challenges'
        AND column_name = 'min_trading_days'
    ) THEN
        RAISE EXCEPTION 'Migration already applied - min_trading_days column exists';
    END IF;
    
    RAISE NOTICE 'Pre-migration validation passed';
END $$;

-- ============================================================================
-- BACKUP RECOMMENDATION
-- ============================================================================

-- IMPORTANT: Always backup before migration!
-- PostgreSQL: pg_dump tradesense > backup_before_migration.sql
-- SQLite: .backup backup_before_migration.db

-- ============================================================================
-- MIGRATION: ADD COLUMN
-- ============================================================================

BEGIN;

-- Step 1: Add new column with default value
-- Using DEFAULT ensures existing rows get a value
ALTER TABLE challenges
ADD COLUMN IF NOT EXISTS min_trading_days INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN challenges.min_trading_days IS 'Minimum number of trading days required to complete challenge';

-- Step 2: Update existing challenges with appropriate defaults
-- Different challenge types may have different requirements
UPDATE challenges
SET min_trading_days = 5
WHERE challenge_type = 'PHASE_1' AND min_trading_days = 0;

UPDATE challenges
SET min_trading_days = 10
WHERE challenge_type = 'PHASE_2' AND min_trading_days = 0;

UPDATE challenges
SET min_trading_days = 3
WHERE challenge_type = 'EVALUATION' AND min_trading_days = 0;

-- Step 3: Add check constraint
ALTER TABLE challenges
ADD CONSTRAINT chk_challenges_min_trading_days_positive
CHECK (min_trading_days >= 0);

-- Step 4: Add index for queries
CREATE INDEX IF NOT EXISTS idx_challenges_min_trading_days
ON challenges (min_trading_days)
WHERE status = 'ACTIVE';

-- Step 5: Update schema version (if using version tracking)
-- INSERT INTO schema_migrations (version, description, applied_at)
-- VALUES ('001', 'Add min_trading_days to challenges', CURRENT_TIMESTAMP);

COMMIT;

-- ============================================================================
-- POST-MIGRATION VALIDATION
-- ============================================================================

-- Verify column was added
DO $$
DECLARE
    column_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO column_count
    FROM information_schema.columns
    WHERE table_name = 'challenges'
    AND column_name = 'min_trading_days';
    
    IF column_count = 1 THEN
        RAISE NOTICE 'Migration successful - min_trading_days column added';
    ELSE
        RAISE EXCEPTION 'Migration failed - column not found';
    END IF;
END $$;

-- Verify data integrity
DO $$
DECLARE
    null_count INTEGER;
    negative_count INTEGER;
BEGIN
    -- Check for NULL values (should be none)
    SELECT COUNT(*) INTO null_count
    FROM challenges
    WHERE min_trading_days IS NULL;
    
    IF null_count > 0 THEN
        RAISE EXCEPTION 'Data integrity issue - % NULL values found', null_count;
    END IF;
    
    -- Check for negative values (should be none)
    SELECT COUNT(*) INTO negative_count
    FROM challenges
    WHERE min_trading_days < 0;
    
    IF negative_count > 0 THEN
        RAISE EXCEPTION 'Data integrity issue - % negative values found', negative_count;
    END IF;
    
    RAISE NOTICE 'Data integrity validation passed';
END $$;

-- Verify constraint was added
DO $$
DECLARE
    constraint_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO constraint_count
    FROM information_schema.table_constraints
    WHERE table_name = 'challenges'
    AND constraint_name = 'chk_challenges_min_trading_days_positive';
    
    IF constraint_count = 1 THEN
        RAISE NOTICE 'Constraint validation passed';
    ELSE
        RAISE WARNING 'Constraint not found - may need manual verification';
    END IF;
END $$;

-- Verify index was created
DO $$
DECLARE
    index_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE tablename = 'challenges'
    AND indexname = 'idx_challenges_min_trading_days';
    
    IF index_count = 1 THEN
        RAISE NOTICE 'Index validation passed';
    ELSE
        RAISE WARNING 'Index not found - may need manual verification';
    END IF;
END $$;

-- ============================================================================
-- ROLLBACK SCRIPT (IF NEEDED)
-- ============================================================================

-- CAUTION: Only run this if migration needs to be rolled back
-- This will remove the column and all data in it

/*
BEGIN;

-- Remove index
DROP INDEX IF EXISTS idx_challenges_min_trading_days;

-- Remove constraint
ALTER TABLE challenges
DROP CONSTRAINT IF EXISTS chk_challenges_min_trading_days_positive;

-- Remove column (CAUTION: Data loss!)
ALTER TABLE challenges
DROP COLUMN IF EXISTS min_trading_days;

-- Update schema version (if using version tracking)
-- DELETE FROM schema_migrations WHERE version = '001';

COMMIT;

-- Verify rollback
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'challenges'
        AND column_name = 'min_trading_days'
    ) THEN
        RAISE NOTICE 'Rollback successful - column removed';
    ELSE
        RAISE EXCEPTION 'Rollback failed - column still exists';
    END IF;
END $$;
*/

-- ============================================================================
-- APPLICATION CODE CHANGES REQUIRED
-- ============================================================================

/*
After this migration, update application code:

1. Challenge Creation:
   - Include min_trading_days in INSERT statements
   - Validate min_trading_days based on challenge_type

2. Challenge Validation:
   - Check trading_days >= min_trading_days before funding
   - Add rule evaluation for minimum trading days

3. API Responses:
   - Include min_trading_days in challenge DTOs
   - Update API documentation

4. Frontend:
   - Display min_trading_days requirement to users
   - Show progress towards minimum trading days

Example Python code:

```python
# Challenge creation
@dataclass
class CreateChallengeCommand:
    user_id: UUID
    challenge_type: str
    initial_balance: Decimal
    min_trading_days: int = 5  # New field

# Challenge validation
def can_fund_challenge(challenge: Challenge) -> bool:
    trading_days = (challenge.last_trade_at - challenge.started_at).days
    
    if trading_days < challenge.min_trading_days:
        return False  # Not enough trading days
    
    # Check other requirements...
    return True
```

Example SQL query:

```sql
-- Get challenges with trading days progress
SELECT
    c.id,
    c.min_trading_days,
    EXTRACT(DAY FROM (c.last_trade_at - c.started_at)) as current_trading_days,
    CASE
        WHEN EXTRACT(DAY FROM (c.last_trade_at - c.started_at)) >= c.min_trading_days
        THEN 'REQUIREMENT_MET'
        ELSE 'IN_PROGRESS'
    END as trading_days_status
FROM challenges c
WHERE c.status = 'ACTIVE';
```
*/

-- ============================================================================
-- TESTING CHECKLIST
-- ============================================================================

/*
Before deploying to production:

□ Migration tested on development database
□ Migration tested on staging database with production-like data
□ Rollback tested and verified
□ Application code updated and tested
□ API tests updated and passing
□ Integration tests updated and passing
□ Performance impact assessed (should be minimal)
□ Backup created before migration
□ Rollback plan documented and ready
□ Team notified of migration schedule
□ Monitoring alerts configured
□ Post-migration validation queries prepared

During deployment:
□ Run migration during low-traffic period
□ Monitor database performance
□ Monitor application logs for errors
□ Run post-migration validation queries
□ Verify application functionality
□ Monitor for 24 hours after deployment

If issues occur:
□ Execute rollback script immediately
□ Restore from backup if needed
□ Investigate root cause
□ Fix issues and retry migration
*/

-- ============================================================================
-- PERFORMANCE IMPACT ASSESSMENT
-- ============================================================================

-- Expected impact: MINIMAL
-- - Adding column with DEFAULT: Fast (no table rewrite in PostgreSQL 11+)
-- - Updating existing rows: Fast (small table, indexed)
-- - Adding constraint: Fast (validation only)
-- - Adding index: Fast (small table, partial index)

-- Estimated downtime: NONE (online migration)
-- Estimated duration: < 1 second for small tables, < 10 seconds for large tables

-- ============================================================================
-- MONITORING QUERIES
-- ============================================================================

-- Monitor migration progress (for large tables)
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename = 'challenges';

-- Check for blocking queries
SELECT
    pid,
    usename,
    application_name,
    state,
    query,
    wait_event_type,
    wait_event
FROM pg_stat_activity
WHERE datname = current_database()
AND state != 'idle'
ORDER BY query_start;

-- ============================================================================
-- COMPLETION SUMMARY
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Migration 001 completed successfully!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Changes:';
    RAISE NOTICE '  - Added min_trading_days column to challenges table';
    RAISE NOTICE '  - Updated existing challenges with default values';
    RAISE NOTICE '  - Added check constraint for data validation';
    RAISE NOTICE '  - Added index for query performance';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Update application code to use new field';
    RAISE NOTICE '  2. Update API documentation';
    RAISE NOTICE '  3. Update frontend to display requirement';
    RAISE NOTICE '  4. Monitor for 24 hours';
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
