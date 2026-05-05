CREATE TABLE IF NOT EXISTS klines (
    symbol VARCHAR(20),
    interval VARCHAR(10),
    date_bucket DATE,
    timestamp BIGINT,
    open VARCHAR(30),
    high VARCHAR(30),
    low VARCHAR(30),
    close VARCHAR(30),
    volume VARCHAR(30),
    PRIMARY KEY (symbol, interval, date_bucket, timestamp)
);

CREATE TABLE IF NOT EXISTS orderbooks (
    symbol VARCHAR(20),
    date_bucket DATE,
    timestamp BIGINT,
    bids TEXT,
    asks TEXT,
    PRIMARY KEY (symbol, date_bucket, timestamp)
);
