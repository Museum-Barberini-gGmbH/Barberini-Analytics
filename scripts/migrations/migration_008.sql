-- Revise social media views (#187), add permalinks (#137) and rename constraints
BEGIN;

    -- A. Drop old views
    DROP VIEW post;
    DROP VIEW app_review;


    /** B. Alter tables to add museum-specific service id and generated
        columns
      * Recreate tables if necessary because they are not optimized anyway and
      * psql does not allow to insert a column at a different position than
      * the end.
      */
    DROP TABLE appstore_review;
    CREATE TABLE appstore_review (
        app_id text NOT NULL,
        review_id text NOT NULL,
        PRIMARY KEY (app_id, review_id),
        appstore_review_id text
            GENERATED ALWAYS AS (
                app_id || '_' || review_id
            ) STORED,
        text text,
        rating int,
        app_version text,
        vote_count integer,
        vote_sum int,
        title text,
        post_date timestamp,
        country_code text,
        permalink text
            GENERATED ALWAYS AS (
                'https://apps.apple.com/de/app/museum-barberini/id'
                    || app_id
                    || '#see-all/reviews'
                -- Apple seems not to support review-specific URLs
            ) STORED
    );

    /** In order to keep old facebook data, we will do the following:
      * 1. Decouple performance table from post table
      * 2. Create a backup of the post table
      * 3. Recreate and refill post table
      * 4. Reconnect the performance table
      */
    -- 1. Decouple performance table from post table
    ALTER TABLE fb_post_performance
        DROP CONSTRAINT fb_post_performance_fb_post_id_fkey;
    -- 2. Backup old posts
    ALTER TABLE fb_post rename TO fb_post_old;
    ALTER TABLE fb_post_old DROP CONSTRAINT fb_post_pkey;
    -- 3a. Recreate post table
    CREATE TABLE fb_post (
        page_id text NOT NULL,
        post_id text NOT NULL,
        PRIMARY KEY (page_id, post_id),
        fb_post_id text
            GENERATED ALWAYS AS (
                page_id || '_' || post_id
            ) STORED,
        post_date timestamp,
        text text,
        permalink TEXT
            GENERATED ALWAYS AS (
                'https://www.facebook.com/' || page_id
                    || '/posts/' || post_id
            ) STORED
    );
    ALTER TABLE fb_post_performance
        RENAME COLUMN time_stamp TO "timestamp",
        ADD COLUMN page_id text,
        ADD COLUMN post_id text;
    -- 3b. Refill post table
    INSERT INTO fb_post (page_id, post_id, post_date, text)
        SELECT old_post_id[1] as page_id, old_post_id[2] AS post_id, post_date, text
        FROM fb_post_old, regexp_matches(fb_post_id, '^(\d+)_(\d+)$') AS old_post_id;
        -- unfortunately O(n²) because inter-row updates appear impossible
    -- 4. Reconnect performance table
    UPDATE fb_post_performance AS perf
        SET perf.page_id = fb_post.page_id, perf.post_id = fb_post.post_id
        FROM fb_post
        WHERE fb_post.fb_post_id = perf.fb_post_id;
    ALTER TABLE fb_post_performance
        ALTER COLUMN page_id SET NOT NULL,
        ALTER COLUMN post_id SET NOT NULL,
        DROP COLUMN fb_post_id,
        ADD PRIMARY KEY (page_id, post_id, timestamp),
        ADD FOREIGN KEY (page_id, post_id) REFERENCES fb_post;
    -- 5. Clean up
    DROP TABLE fb_post_old;

    ALTER TABLE google_maps_review
        ADD COLUMN place_id TEXT;
    ALTER TABLE google_maps_review
        ADD COLUMN permalink TEXT
        GENERATED ALWAYS AS (
            'https://maps.google.com/maps?cid=' || place_id
            /** GMB API does not provide option to create permalink for
              * google_maps_review_id. See also:
              * https://support.google.com/business/thread/11131183
              */
        ) STORED;

    ALTER TABLE gplay_review
        ADD COLUMN app_id text,
        ADD COLUMN permalink TEXT
        GENERATED ALWAYS AS (
            'https://play.google.com/store/apps/details'
                || '?id=' || app_id
                || '&reviewId=' || playstore_review_id
        ) STORED;

    ALTER TABLE tweet 
        ADD COLUMN permalink TEXT
        GENERATED ALWAYS AS (
            'https://twitter.com/user/status/' || tweet_id
        ) STORED;


    -- C. Create new views
    CREATE VIEW app_review AS
    (
        SELECT
            'Apple Appstore' AS source,
            appstore_review_id AS review_id,
            NULLIF(CONCAT_WS(E'\n', title, text), '') AS text,
            post_date,
            rating,
            app_version,
            NULL AS likes,
            title,
            permalink
        FROM appstore_review
        WHERE app_id = '1150432552'  -- Museum Barberini
    ) UNION (
        SELECT
            'Google Play' AS source,
            playstore_review_id AS review_id,
            text,
            post_date,
            rating,
            app_version,
            thumbs_up AS likes,
            NULL as title,
            permalink
        FROM gplay_review
        WHERE app_id = 'com.barberini.museum.barberinidigital'
    );

    CREATE VIEW social_media_post AS (
        SELECT
            'Facebook' AS source,
            fb_post_id AS post_id,
            text,
            post_date,
            NULL as media_type,
            NULL as response_to,
            NULL as user_id,
            TRUE as is_promotion,
            likes,
            comments,
            shares,
            
    ) UNION (
        SELECT
            'Twitter' AS source,
            tweet_id AS post_id,
            text,
            post_date,
            NULL as media_type,
            response_to,
            user_id,
            is_promotion,
            likes,
            replies AS comments,
            retweets AS shares,
            permalink
        FROM tweet
        NATURAL JOIN (
            SELECT tweet_id, likes, replies, retweets
            FROM tweet_performance tp1
            WHERE EXISTS(
                SELECT tp2.tweet_id
                FROM tweet_performance tp2
                WHERE tp2.tweet_id = tp1.tweet_id
                GROUP BY tp2.tweet_id, tp2.timestamp
                HAVING MAX(tp2.timestamp) = tp1.timestamp)
        ) AS performance
    )*/

COMMIT;