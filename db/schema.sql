-- =====================================================================
-- 簡易POSアプリ スキーマ作成SQL（MySQL 8.0 / Azure Database for MySQL Flexible Server）
-- 生成元: backend/alembic/versions（alembic upgrade head --sql）
-- 通常は `alembic upgrade head` を使う。手作業で流す場合のみこのファイルを使う。
-- 事前に db/create_schema.sql でスキーマ（データベース）を作成しておくこと。
-- =====================================================================
USE pos_app;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_initial

CREATE TABLE products (
    product_code VARCHAR(13) NOT NULL COMMENT '商品コード（13桁）', 
    product_name VARCHAR(100) NOT NULL COMMENT '商品名称', 
    unit_price INTEGER NOT NULL COMMENT '単価（税抜・円）', 
    is_active BOOL NOT NULL DEFAULT true, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, 
    PRIMARY KEY (product_code), 
    CONSTRAINT ck_products_unit_price CHECK (unit_price >= 0)
)ENGINE=InnoDB COMMENT='商品マスタ' CHARSET=utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE members (
    member_id VARCHAR(7) NOT NULL COMMENT '会員ID（M+6桁）', 
    name VARCHAR(100) NOT NULL, 
    phone VARCHAR(20), 
    address VARCHAR(255), 
    gender VARCHAR(10), 
    age SMALLINT, 
    is_active BOOL NOT NULL COMMENT '退会は論理削除' DEFAULT true, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, 
    PRIMARY KEY (member_id)
)ENGINE=InnoDB COMMENT='会員' CHARSET=utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE cashiers (
    cashier_id VARCHAR(20) NOT NULL, 
    cashier_name VARCHAR(50) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL COMMENT 'Argon2id', 
    is_active BOOL NOT NULL DEFAULT true, 
    failed_login_count INTEGER NOT NULL DEFAULT '0', 
    locked_until DATETIME COMMENT 'ログイン失敗ロック期限（UTC）', 
    created_at DATETIME NOT NULL DEFAULT now(), 
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, 
    PRIMARY KEY (cashier_id)
)ENGINE=InnoDB COMMENT='レジ担当者' CHARSET=utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE TABLE sessions (
    session_id_hash VARCHAR(64) NOT NULL COMMENT 'セッションIDのSHA-256', 
    cashier_id VARCHAR(20) NOT NULL, 
    expires_at DATETIME NOT NULL COMMENT 'UTC', 
    created_at DATETIME NOT NULL COMMENT 'UTC', 
    PRIMARY KEY (session_id_hash), 
    CONSTRAINT fk_sessions_cashier FOREIGN KEY(cashier_id) REFERENCES cashiers (cashier_id)
)ENGINE=InnoDB COMMENT='ログインセッション' CHARSET=utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE INDEX ix_sessions_cashier_id ON sessions (cashier_id);

CREATE INDEX ix_sessions_expires_at ON sessions (expires_at);

CREATE TABLE tax_rates (
    tax_rate_id INTEGER NOT NULL AUTO_INCREMENT, 
    sales_mode VARCHAR(10) NOT NULL COMMENT 'DINE_IN / TAKEOUT', 
    rate NUMERIC(5, 4) NOT NULL COMMENT '例: 0.1000', 
    effective_from DATE NOT NULL COMMENT '適用開始日（JST）', 
    effective_to DATE COMMENT '適用終了日（JST、NULL=期限なし）', 
    rounding_method VARCHAR(10) NOT NULL COMMENT 'FLOOR / HALF_UP / CEIL' DEFAULT 'FLOOR', 
    created_at DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (tax_rate_id), 
    CONSTRAINT ck_tax_rates_sales_mode CHECK (sales_mode IN ('DINE_IN','TAKEOUT')), 
    CONSTRAINT ck_tax_rates_rounding CHECK (rounding_method IN ('FLOOR','HALF_UP','CEIL')), 
    CONSTRAINT ck_tax_rates_rate CHECK (rate >= 0 AND rate < 1)
)ENGINE=InnoDB COMMENT='消費税率マスタ（期間管理）' CHARSET=utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE INDEX ix_tax_rates_mode_from ON tax_rates (sales_mode, effective_from);

CREATE TABLE transactions (
    transaction_id BIGINT NOT NULL COMMENT '内部連番' AUTO_INCREMENT, 
    transaction_no VARCHAR(32) COMMENT '対外表示用ID（T+日付+連番）', 
    transaction_at DATETIME NOT NULL COMMENT '取引日時（UTC）', 
    member_id VARCHAR(7) COMMENT '非会員はNULL', 
    cashier_id VARCHAR(20) NOT NULL, 
    sales_mode VARCHAR(10) NOT NULL, 
    subtotal_excl_tax BIGINT NOT NULL, 
    tax_amount BIGINT NOT NULL, 
    total_incl_tax BIGINT NOT NULL, 
    idempotency_key VARCHAR(36) NOT NULL COMMENT '二重送信対策', 
    created_at DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (transaction_id), 
    CONSTRAINT uq_transactions_transaction_no UNIQUE (transaction_no), 
    CONSTRAINT uq_transactions_idempotency_key UNIQUE (idempotency_key), 
    CONSTRAINT ck_transactions_sales_mode CHECK (sales_mode IN ('DINE_IN','TAKEOUT')), 
    CONSTRAINT fk_transactions_member FOREIGN KEY(member_id) REFERENCES members (member_id), 
    CONSTRAINT fk_transactions_cashier FOREIGN KEY(cashier_id) REFERENCES cashiers (cashier_id)
)ENGINE=InnoDB COMMENT='取引（ヘッダ）' CHARSET=utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE INDEX ix_transactions_transaction_at ON transactions (transaction_at);

CREATE INDEX ix_transactions_cashier_id ON transactions (cashier_id);

CREATE INDEX ix_transactions_member_id ON transactions (member_id);

CREATE TABLE transaction_items (
    transaction_item_id BIGINT NOT NULL AUTO_INCREMENT, 
    transaction_id BIGINT NOT NULL, 
    line_no SMALLINT NOT NULL, 
    product_code VARCHAR(13) NOT NULL, 
    product_name_snapshot VARCHAR(100) NOT NULL, 
    unit_price_snapshot INTEGER NOT NULL, 
    quantity SMALLINT NOT NULL, 
    tax_rate_snapshot NUMERIC(5, 4) NOT NULL, 
    line_subtotal BIGINT NOT NULL, 
    line_tax BIGINT NOT NULL, 
    line_total BIGINT NOT NULL, 
    PRIMARY KEY (transaction_item_id), 
    CONSTRAINT uq_items_transaction_line UNIQUE (transaction_id, line_no), 
    CONSTRAINT ck_transaction_items_quantity CHECK (quantity >= 1), 
    CONSTRAINT fk_items_transaction FOREIGN KEY(transaction_id) REFERENCES transactions (transaction_id), 
    CONSTRAINT fk_items_product FOREIGN KEY(product_code) REFERENCES products (product_code)
)ENGINE=InnoDB COMMENT='取引明細（確定時スナップショット）' CHARSET=utf8mb4 COLLATE utf8mb4_0900_bin;

CREATE INDEX ix_transaction_items_transaction_id ON transaction_items (transaction_id);

INSERT INTO alembic_version (version_num) VALUES ('0001_initial');

