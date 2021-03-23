-- Integrate gomus quotas and capacities (!377)

BEGIN;

    CREATE TABLE gomus_quota (
        quota_id INT PRIMARY KEY,
        name TEXT,
        creation_date TIMESTAMP,
        update_date TIMESTAMP
    );

    CREATE TABLE gomus_capacity (
        quota_id INT REFERENCES gomus_quota,
        date DATE,
        time TIME,
        max INT,
        sold INT,
        reserved INT,
        available INT,
        CHECK (max - sold - reserved = available),
        last_updated TIMESTAMP,
        PRIMARY KEY (quota_id, date, time)
    );

COMMIT;
