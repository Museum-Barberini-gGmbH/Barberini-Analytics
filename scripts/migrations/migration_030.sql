-- Gomus: Add unique entries to entry tables (!264)

BEGIN;

    ALTER TABLE gomus_daily_entry ADD COLUMN unique_count INTEGER;
    ALTER TABLE gomus_expected_daily_entry ADD COLUMN unique_count INTEGER;

COMMIT;
