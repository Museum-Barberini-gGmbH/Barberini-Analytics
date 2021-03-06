-- Create tables for Instagram (!133)

BEGIN;

    CREATE TABLE ig_post (
        ig_post_id  TEXT,
        text        TEXT,
        post_date   TIMESTAMP,
        media_type  TEXT,
        likes       INT,
        comments    INT,
        permalink   TEXT
    );
    ALTER TABLE ig_post
        ADD CONSTRAINT  ig_post_primkey
        PRIMARY KEY     (ig_post_id);

    CREATE TABLE ig_post_performance (
        ig_post_id  TEXT,
        timestamp   TIMESTAMP,
        impressions INT,
        reach       INT,
        engagement  INT,
        saved       INT,
        video_views INT
    );
    ALTER TABLE ig_post_performance
        ADD CONSTRAINT  ig_post_performance_primkey
        PRIMARY KEY     (ig_post_id, timestamp);

    CREATE TABLE ig_audience_origin (
        city    TEXT,
        amount  INT
    );
    ALTER TABLE ig_audience_origin
        ADD CONSTRAINT  ig_audience_origin_primkey
        PRIMARY KEY     (city);

    CREATE TABLE ig_audience_gender_age (
        gender  TEXT,
        age     TEXT,
        amount  INT
    );
    ALTER TABLE ig_audience_gender_age
        ADD CONSTRAINT  ig_audience_gender_age_primkey
        PRIMARY KEY     (gender, age);


    ALTER TABLE ig_post_performance
        ADD CONSTRAINT  ig_post_id_fkey
        FOREIGN KEY     (ig_post_id)
        REFERENCES      ig_post (ig_post_id)
        ON UPDATE       CASCADE;

COMMIT;
