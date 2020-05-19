BEGIN;
CREATE TABLE fb_post_comment (
    comment_id TEXT PRIMARY KEY,
    page_id TEXT,
    post_id TEXT,
    post_date TIMESTAMP,
    message TEXT,
    from_barberini BOOLEAN,
    parent TEXT,
    -- "parent TEXT REFERENCES fb_post_comment" does not work
    -- because ensure_foreign_keys would delete values which
    -- are not yet in the DB, although it would be more semantically precise
    FOREIGN KEY (page_id, post_id) REFERENCES fb_post
);

COMMIT;
