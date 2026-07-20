-- ==========================================================
-- WM Portfolio mock schema (real domain names)
-- ==========================================================

CREATE TABLE IF NOT EXISTS portfolio_transactions (
    txn_id VARCHAR(50) PRIMARY KEY COMMENT 'Transaction id',
    user_id VARCHAR(50) NOT NULL COMMENT 'Client id',
    instrument_id VARCHAR(50) NOT NULL COMMENT 'Instrument id',
    instrument_name VARCHAR(100) NOT NULL COMMENT 'Instrument display name',
    side VARCHAR(20) NOT NULL COMMENT 'Buy / Sell / Dividend / Fee / Deposit',
    quantity DECIMAL(18, 4) NOT NULL DEFAULT 0 COMMENT 'Quantity',
    amount DECIMAL(18, 2) NOT NULL COMMENT 'Signed amount in currency',
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    status VARCHAR(20) NOT NULL COMMENT 'Settled / Pending / Cancelled',
    trade_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Portfolio transactions';

TRUNCATE TABLE portfolio_transactions;

INSERT INTO portfolio_transactions
(txn_id, user_id, instrument_id, instrument_name, side, quantity, amount, currency, status, trade_date) VALUES
('TXN-1001-001', 'user_1001', 'EQ_AAPL', 'Apple Inc.', 'Buy', 50.0000, -9500.00, 'USD', 'Settled', '2025-10-01 10:00:00'),
('TXN-1001-002', 'user_1001', 'BD_UST10Y', 'US Treasury 10Y Note ETF', 'Buy', 100.0000, -9800.00, 'USD', 'Settled', '2025-10-05 14:30:00'),
('TXN-1001-003', 'user_1001', 'EQ_AAPL', 'Apple Inc.', 'Dividend', 0.0000, 86.50, 'USD', 'Settled', '2026-01-15 08:15:00'),
('TXN-1001-004', 'user_1001', 'MF_SP500', 'S&P 500 Index Fund', 'Buy', 80.0000, -12000.00, 'USD', 'Settled', '2026-02-01 09:00:00'),
('TXN-1001-005', 'user_1001', 'CASH_USD', 'USD Cash', 'Fee', 0.0000, -12.00, 'USD', 'Settled', '2026-07-01 16:00:00'),
('TXN-1002-001', 'user_1002', 'EQ_MSFT', 'Microsoft Corp.', 'Buy', 20.0000, -8400.00, 'USD', 'Settled', '2025-11-15 09:00:00'),
('TXN-1002-002', 'user_1002', 'CASH_USD', 'USD Cash', 'Deposit', 0.0000, 2000.00, 'USD', 'Settled', '2025-11-15 09:05:00'),
('TXN-1002-003', 'user_1002', 'EQ_MSFT', 'Microsoft Corp.', 'Sell', 5.0000, 2100.00, 'USD', 'Pending', '2026-06-16 10:00:00');

CREATE TABLE IF NOT EXISTS portfolio_holdings (
    position_id VARCHAR(50) PRIMARY KEY COMMENT 'Position id',
    user_id VARCHAR(50) NOT NULL COMMENT 'Client id',
    instrument_id VARCHAR(50) NOT NULL,
    instrument_name VARCHAR(100) NOT NULL,
    asset_class VARCHAR(50) NOT NULL,
    sector VARCHAR(50) NOT NULL,
    quantity DECIMAL(18, 4) NOT NULL DEFAULT 0,
    market_value DECIMAL(18, 2) NOT NULL DEFAULT 0,
    weight_pct DECIMAL(8, 2) NOT NULL DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    status VARCHAR(20) NOT NULL COMMENT 'Open / Closed',
    as_of DATE NOT NULL,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Current portfolio holdings';

TRUNCATE TABLE portfolio_holdings;

INSERT INTO portfolio_holdings
(position_id, user_id, instrument_id, instrument_name, asset_class, sector, quantity, market_value, weight_pct, currency, status, as_of) VALUES
('pos-user1001-aapl', 'user_1001', 'EQ_AAPL', 'Apple Inc.', 'Equity', 'Technology', 50.0000, 11200.00, 28.50, 'USD', 'Open', CURDATE()),
('pos-user1001-ust', 'user_1001', 'BD_UST10Y', 'US Treasury 10Y Note ETF', 'Fixed Income', 'Government', 100.0000, 9420.00, 24.00, 'USD', 'Open', CURDATE()),
('pos-user1001-spx', 'user_1001', 'MF_SP500', 'S&P 500 Index Fund', 'Fund', 'Broad Market', 80.0000, 12570.00, 32.00, 'USD', 'Open', CURDATE()),
('pos-user1001-cash', 'user_1001', 'CASH_USD', 'USD Cash', 'Cash', 'Cash', 1.0000, 6090.00, 15.50, 'USD', 'Open', CURDATE()),
('pos-user1002-msft', 'user_1002', 'EQ_MSFT', 'Microsoft Corp.', 'Equity', 'Technology', 15.0000, 7800.00, 78.00, 'USD', 'Open', CURDATE()),
('pos-user1002-cash', 'user_1002', 'CASH_USD', 'USD Cash', 'Cash', 'Cash', 1.0000, 2200.00, 22.00, 'USD', 'Open', CURDATE());

CREATE TABLE IF NOT EXISTS position_risk_daily (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    position_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    metric_date DATE NOT NULL,
    volatility_proxy_pct DECIMAL(8, 2) NOT NULL,
    weight_pct DECIMAL(8, 2) NOT NULL,
    beta_proxy DECIMAL(8, 2) NOT NULL,
    INDEX idx_position_date (position_id, metric_date),
    INDEX idx_user_position (user_id, position_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Daily position risk proxies';

TRUNCATE TABLE position_risk_daily;

INSERT INTO position_risk_daily (position_id, user_id, metric_date, volatility_proxy_pct, weight_pct, beta_proxy) VALUES
('pos-user1001-aapl', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 6 DAY), 22.10, 28.50, 1.15),
('pos-user1001-aapl', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 5 DAY), 23.50, 28.40, 1.18),
('pos-user1001-aapl', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 4 DAY), 21.20, 28.60, 1.12),
('pos-user1001-aapl', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 3 DAY), 24.90, 28.70, 1.20),
('pos-user1001-aapl', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 2 DAY), 22.80, 28.50, 1.16),
('pos-user1001-aapl', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 1 DAY), 23.40, 28.55, 1.17),
('pos-user1001-aapl', 'user_1001', CURDATE(), 22.00, 28.50, 1.14),
('pos-user1001-ust', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 6 DAY), 8.10, 24.00, 0.35),
('pos-user1001-ust', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 5 DAY), 7.50, 24.10, 0.32),
('pos-user1001-ust', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 4 DAY), 9.20, 23.90, 0.38),
('pos-user1001-ust', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 3 DAY), 8.90, 24.00, 0.36),
('pos-user1001-ust', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 2 DAY), 7.80, 24.05, 0.34),
('pos-user1001-ust', 'user_1001', DATE_SUB(CURDATE(), INTERVAL 1 DAY), 8.40, 24.00, 0.35),
('pos-user1001-ust', 'user_1001', CURDATE(), 8.00, 24.00, 0.33),
('pos-user1002-msft', 'user_1002', DATE_SUB(CURDATE(), INTERVAL 6 DAY), 26.50, 78.10, 1.05),
('pos-user1002-msft', 'user_1002', DATE_SUB(CURDATE(), INTERVAL 5 DAY), 28.20, 77.80, 1.08),
('pos-user1002-msft', 'user_1002', DATE_SUB(CURDATE(), INTERVAL 4 DAY), 25.40, 78.20, 1.02),
('pos-user1002-msft', 'user_1002', DATE_SUB(CURDATE(), INTERVAL 3 DAY), 29.00, 78.50, 1.10),
('pos-user1002-msft', 'user_1002', DATE_SUB(CURDATE(), INTERVAL 2 DAY), 27.10, 78.00, 1.06),
('pos-user1002-msft', 'user_1002', DATE_SUB(CURDATE(), INTERVAL 1 DAY), 28.80, 77.90, 1.07),
('pos-user1002-msft', 'user_1002', CURDATE(), 27.30, 78.00, 1.04);
