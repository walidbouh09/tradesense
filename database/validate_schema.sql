-- ============================================================================
-- Schema Validation Script
-- ============================================================================
-- Purpose: Verify that the TradeSense AI schema is correctly installed
-- Usage: Run this after installing the schema to validate everything is working
-- ============================================================================

-- ============================================================================
-- 1. TABLE EXISTENCE VALIDATION
-- ============================================================================

DO $$
DECLARE
    table_count INTEGER;
    expected_tables TEXT[] := ARRAY['users', 'challenges', 'trades', 'challenge_events', 'payments', 'risk_alerts'];
    missing_tables TEXT[];
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VALIDATING TABLE EXISTENCE';
    RAISE NOTICE '========================================';
    
    -- Check each expected table
    SELECT ARRAY_AGG(table_name)
    INTO missing_tables
    FROM (
        SELECT unnest(expected_tables) AS table_name
        EXCEPT
        SELECT table_name::TEXT
        FROM information_schema.tables
        WHERE table_schema = 'public'
    ) AS missing;
    
    IF missing_tables IS NULL THEN
        RAISE NOTICE '✓ All 6 core tables exist';
    ELSE
        RAISE EXCEPTION '✗ Missing tables: %', array_to_string(missing_tables, ', ');
    END IF;
END $$;

-- ============================================================================
-- 2. COLUMN VALIDATION
-- ============================================================================

DO $$
DECLARE
    users_columns INTEGER;
    challenges_columns INTEGER;
    trades_columns INTEGER;
    events_columns INTEGER;
    payments_columns INTEGER;
    alerts_columns INTEGER;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VALIDATING TABLE COLUMNS';
    RAISE NOTICE '========================================';
    
    -- Count columns in each table
    SELECT COUNT(*) INTO users_columns
    FROM information_schema.columns
    WHERE table_name = 'users';
    
    SELECT COUNT(*) INTO challenges_columns
    FROM information_schema.columns
    WHERE table_name = 'challenges';
    
    SELECT COUNT(*) INTO trades_columns
    FROM information_schema.columns
    WHERE table_name = 'trades';
    
    SELECT COUNT(*) INTO events_columns
    FROM information_schema.columns
    WHERE table_name = 'challenge_events';
    
    SELECT COUNT(*) INTO payments_columns
    FROM information_schema.columns
    WHERE table_name = 'payments';
    
    SELECT COUNT(*) INTO alerts_columns
    FROM information_schema.columns
    WHERE table_name = 'risk_alerts';
    
    -- Validate column counts
    IF users_columns >= 12 THEN
        RAISE NOTICE '✓ users table has % columns', users_columns;
    ELSE
        RAISE WARNING '✗ users table has only % columns (expected >= 12)', users_columns;
    END IF;
    
    IF challenges_columns >= 25 THEN
        RAISE NOTICE '✓ challenges table has % columns', challenges_columns;
    ELSE
        RAISE WARNING '✗ challenges table has only % columns (expected >= 25)', challenges_columns;
    END IF;
    
    IF trades_columns >= 12 THEN
        RAISE NOTICE '✓ trades table has % columns', trades_columns;
    ELSE
        RAISE WARNING '✗ trades table has only % columns (expected >= 12)', trades_columns;
    END IF;
    
    IF events_columns >= 11 THEN
        RAISE NOTICE '✓ challenge_events table has % columns', events_columns;
    ELSE
        RAISE WARNING '✗ challenge_events table has only % columns (expected >= 11)', events_columns;
    END IF;
    
    IF payments_columns >= 22 THEN
        RAISE NOTICE '✓ payments table has % columns', payments_columns;
    ELSE
        RAISE WARNING '✗ payments table has only % columns (expected >= 22)', payments_columns;
    END IF;
    
    IF alerts_columns >= 16 THEN
        RAISE NOTICE '✓ risk_alerts table has % columns', alerts_columns;
    ELSE
        RAISE WARNING '✗ risk_alerts table has only % columns (expected >= 16)', alerts_columns;
    END IF;
END $$;

-- ============================================================================
-- 3. FOREIGN KEY VALIDATION
-- ============================================================================

DO $$
DECLARE
    fk_count INTEGER;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VALIDATING FOREIGN KEYS';
    RAISE NOTICE '========================================';
    
    SELECT COUNT(*) INTO fk_count
    FROM information_schema.table_constraints
    WHERE constraint_type = 'FOREIGN KEY'
    AND table_schema = 'public';
    
    IF fk_count >= 8 THEN
        RAISE NOTICE '✓ Found % foreign key constraints', fk_count;
    ELSE
        RAISE WARNING '✗ Found only % foreign key constraints (expected >= 8)', fk_count;
    END IF;
    
    -- List all foreign keys
    RAISE NOTICE '';
    RAISE NOTICE 'Foreign key relationships:';
    FOR fk_count IN
        SELECT 1
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
    LOOP
        RAISE NOTICE '  - % (%) → % (%)',
            kcu.table_name,
            kcu.column_name,
            ccu.table_name,
            ccu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public';
    END LOOP;
END $$;

-- ============================================================================
-- 4. INDEX VALIDATION
-- ============================================================================

DO $$
DECLARE
    index_count INTEGER;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VALIDATING INDEXES';
    RAISE NOTICE '========================================';
    
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE schemaname = 'public';
    
    IF index_count >= 40 THEN
        RAISE NOTICE '✓ Found % indexes', index_count;
    ELSE
        RAISE WARNING '✗ Found only % indexes (expected >= 40)', index_count;
    END IF;
    
    -- Check critical indexes
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_email_active') THEN
        RAISE NOTICE '✓ Critical index: idx_users_email_active';
    ELSE
        RAISE WARNING '✗ Missing critical index: idx_users_email_active';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_challenges_user_id') THEN
        RAISE NOTICE '✓ Critical index: idx_challenges_user_id';
    ELSE
        RAISE WARNING '✗ Missing critical index: idx_challenges_user_id';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_trades_challenge_id') THEN
        RAISE NOTICE '✓ Critical index: idx_trades_challenge_id';
    ELSE
        RAISE WARNING '✗ Missing critical index: idx_trades_challenge_id';
    END IF;
END $$;

-- ============================================================================
-- 5. CONSTRAINT VALIDATION
-- ============================================================================

DO $$
DECLARE
    check_count INTEGER;
    unique_count INTEGER;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VALIDATING CONSTRAINTS';
    RAISE NOTICE '========================================';
    
    -- Check constraints
    SELECT COUNT(*) INTO check_count
    FROM information_schema.table_constraints
    WHERE constraint_type = 'CHECK'
    AND table_schema = 'public';
    
    IF check_count >= 30 THEN
        RAISE NOTICE '✓ Found % check constraints', check_count;
    ELSE
        RAISE WARNING '✗ Found only % check constraints (expected >= 30)', check_count;
    END IF;
    
    -- Unique constraints
    SELECT COUNT(*) INTO unique_count
    FROM information_schema.table_constraints
    WHERE constraint_type = 'UNIQUE'
    AND table_schema = 'public';
    
    IF unique_count >= 10 THEN
        RAISE NOTICE '✓ Found % unique constraints', unique_count;
    ELSE
        RAISE WARNING '✗ Found only % unique constraints (expected >= 10)', unique_count;
    END IF;
END $$;

-- ============================================================================
-- 6. TRIGGER VALIDATION
-- ============================================================================

DO $$
DECLARE
    trigger_count INTEGER;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VALIDATING TRIGGERS';
    RAISE NOTICE '========================================';
    
    SELECT COUNT(*) INTO trigger_count
    FROM information_schema.triggers
    WHERE trigger_schema = 'public';
    
    IF trigger_count >= 6 THEN
        RAISE NOTICE '✓ Found % triggers', trigger_count;
    ELSE
        RAISE WARNING '✗ Found only % triggers (expected >= 6)', trigger_count;
    END IF;
    
    -- Check immutability triggers
    IF EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'trg_trades_immutable'
    ) THEN
        RAISE NOTICE '✓ Immutability trigger: trg_trades_immutable';
    ELSE
        RAISE WARNING '✗ Missing immutability trigger: trg_trades_immutable';
    END IF;
    
    IF EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'trg_challenge_events_immutable'
    ) THEN
        RAISE NOTICE '✓ Immutability trigger: trg_challenge_events_immutable';
    ELSE
        RAISE WARNING '✗ Missing immutability trigger: trg_challenge_events_immutable';
    END IF;
END $$;

-- ============================================================================
-- 7. VIEW VALIDATION
-- ============================================================================

DO $$
DECLARE
    view_count INTEGER;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VALIDATING VIEWS';
    RAISE NOTICE '========================================';
    
    SELECT COUNT(*) INTO view_count
    FROM information_schema.views
    WHERE table_schema = 'public';
    
    IF view_count >= 1 THEN
        RAISE NOTICE '✓ Found % views', view_count;
    ELSE
        RAISE WARNING '✗ Found only % views (expected >= 1)', view_count;
    END IF;
    
    -- Check specific views
    IF EXISTS (
        SELECT 1 FROM information_schema.views
        WHERE table_name = 'challenge_performance_analytics'
    ) THEN
        RAISE NOTICE '✓ View exists: challenge_performance_analytics';
    ELSE
        RAISE WARNING '✗ Missing view: challenge_performance_analytics';
    END IF;
END $$;

-- ============================================================================
-- 8. SAMPLE DATA VALIDATION
-- ============================================================================

DO $$
DECLARE
    admin_count INTEGER;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VALIDATING SAMPLE DATA';
    RAISE NOTICE '========================================';
    
    SELECT COUNT(*) INTO admin_count
    FROM users
    WHERE role = 'SUPERADMIN'
    AND email = 'admin@tradesense.ai';
    
    IF admin_count = 1 THEN
        RAISE NOTICE '✓ Default admin user exists';
    ELSE
        RAISE WARNING '✗ Default admin user not found';
    END IF;
END $$;

-- ============================================================================
-- 9. IMMUTABILITY TEST
-- ============================================================================

DO $$
DECLARE
    test_challenge_id UUID;
    test_trade_id UUID;
    test_event_id UUID;
    immutability_working BOOLEAN := TRUE;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'TESTING IMMUTABILITY ENFORCEMENT';
    RAISE NOTICE '========================================';
    
    -- Create test challenge
    INSERT INTO challenges (
        user_id, challenge_type, initial_balance,
        max_daily_drawdown_percent, max_total_drawdown_percent,
        profit_target_percent, current_equity, max_equity_ever,
        daily_start_equity, daily_max_equity, daily_min_equity
    )
    SELECT
        id, 'TEST', 10000,
        0.05, 0.10, 0.08,
        10000, 10000, 10000, 10000, 10000
    FROM users
    WHERE email = 'admin@tradesense.ai'
    LIMIT 1
    RETURNING id INTO test_challenge_id;
    
    -- Test trade immutability
    BEGIN
        INSERT INTO trades (
            challenge_id, trade_id, symbol, side,
            quantity, price, realized_pnl, commission,
            executed_at, sequence_number
        ) VALUES (
            test_challenge_id, 'TEST_TRADE', 'EURUSD', 'BUY',
            1000, 1.0850, 100, 5,
            CURRENT_TIMESTAMP, 1
        ) RETURNING id INTO test_trade_id;
        
        -- Try to update (should fail)
        UPDATE trades SET realized_pnl = 999 WHERE id = test_trade_id;
        
        -- If we get here, immutability is NOT working
        immutability_working := FALSE;
        RAISE WARNING '✗ Trade immutability NOT enforced!';
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE '✓ Trade immutability enforced (update blocked)';
    END;
    
    -- Test event immutability
    BEGIN
        INSERT INTO challenge_events (
            challenge_id, event_type, sequence_number,
            event_data, description, occurred_at
        ) VALUES (
            test_challenge_id, 'TEST_EVENT', 1,
            '{}'::jsonb, 'Test event', CURRENT_TIMESTAMP
        ) RETURNING id INTO test_event_id;
        
        -- Try to update (should fail)
        UPDATE challenge_events SET description = 'Modified' WHERE id = test_event_id;
        
        -- If we get here, immutability is NOT working
        immutability_working := FALSE;
        RAISE WARNING '✗ Event immutability NOT enforced!';
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE '✓ Event immutability enforced (update blocked)';
    END;
    
    -- Cleanup test data
    DELETE FROM challenge_events WHERE challenge_id = test_challenge_id;
    DELETE FROM trades WHERE challenge_id = test_challenge_id;
    DELETE FROM challenges WHERE id = test_challenge_id;
    
    IF immutability_working THEN
        RAISE NOTICE '✓ Immutability enforcement working correctly';
    ELSE
        RAISE EXCEPTION '✗ CRITICAL: Immutability enforcement FAILED!';
    END IF;
END $$;

-- ============================================================================
-- 10. PERFORMANCE TEST
-- ============================================================================

DO $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    duration INTERVAL;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'TESTING QUERY PERFORMANCE';
    RAISE NOTICE '========================================';
    
    -- Test 1: User lookup by email
    start_time := clock_timestamp();
    PERFORM * FROM users WHERE email = 'admin@tradesense.ai' LIMIT 1;
    end_time := clock_timestamp();
    duration := end_time - start_time;
    
    RAISE NOTICE 'User lookup by email: % ms', EXTRACT(MILLISECONDS FROM duration);
    
    -- Test 2: Challenge query with join
    start_time := clock_timestamp();
    PERFORM c.*, u.email
    FROM challenges c
    JOIN users u ON c.user_id = u.id
    LIMIT 10;
    end_time := clock_timestamp();
    duration := end_time - start_time;
    
    RAISE NOTICE 'Challenge query with join: % ms', EXTRACT(MILLISECONDS FROM duration);
    
    -- Test 3: Analytics view
    start_time := clock_timestamp();
    PERFORM * FROM challenge_performance_analytics LIMIT 10;
    end_time := clock_timestamp();
    duration := end_time - start_time;
    
    RAISE NOTICE 'Analytics view query: % ms', EXTRACT(MILLISECONDS FROM duration);
    
    RAISE NOTICE '✓ Performance tests completed';
END $$;

-- ============================================================================
-- VALIDATION SUMMARY
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VALIDATION COMPLETE';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Schema validation completed successfully!';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Review any warnings above';
    RAISE NOTICE '  2. Run application integration tests';
    RAISE NOTICE '  3. Test with realistic data volumes';
    RAISE NOTICE '  4. Configure monitoring and alerts';
    RAISE NOTICE '  5. Set up backup and recovery procedures';
    RAISE NOTICE '';
    RAISE NOTICE 'For more information, see:';
    RAISE NOTICE '  - SCHEMA_README.md';
    RAISE NOTICE '  - QUICK_REFERENCE.md';
    RAISE NOTICE '  - DELIVERY_SUMMARY.md';
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- END OF VALIDATION
-- ============================================================================
