-- Fix facebook join in social_media_post view (!205)

BEGIN;

    CREATE OR REPLACE VIEW social_media_post AS (
        WITH _social_media_post AS (
            (
                SELECT
                    CASE WHEN is_comment
                        THEN 'Facebook Comment'
                        ELSE 'Facebook Post'
                    END AS source,
                    fb_post_all.post_id,
                    fb_post_all.text,
                    fb_post_all.post_date,
                    NULL AS media_type,
                    response_to,
                    NULL AS user_id,
                    is_from_museum,
                    likes,
                    comments,
                    shares,
                    permalink
                FROM fb_post_all
                LEFT JOIN fb_post_rich
                    ON fb_post_all.post_id = fb_post_rich.fb_post_id
            ) UNION (
                SELECT
                    'Instagram' AS source,
                    ig_post_id AS post_id,
                    text,
                    post_date,
                    media_type,
                    NULL AS response_to,
                    NULL AS user_id,
                    TRUE AS is_from_museum,
                    likes,
                    comments,
                    NULL AS shares,
                    permalink
                FROM ig_post_rich
            ) UNION (
                SELECT
                    'Twitter' AS source,
                    tweet_id AS post_id,
                    text,
                    post_date,
                    NULL as media_type,
                    response_to,
                    user_id,
                    is_from_museum,
                    likes,
                    replies AS comments,
                    retweets AS shares,
                    permalink
                FROM tweet_rich
            )
        )
        SELECT *, (response_to IS NOT NULL) is_response
        FROM _social_media_post
    );

COMMIT;
