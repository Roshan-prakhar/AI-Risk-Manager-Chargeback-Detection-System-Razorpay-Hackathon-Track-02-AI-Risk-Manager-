CREATE TABLE IF NOT EXISTS tier_threshold_config (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    trivial_max_score   DOUBLE NOT NULL,
    moderate_max_score  DOUBLE NOT NULL,
    value_threshold     DOUBLE NOT NULL,
    computed_at         TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS tier_assignments (
    transaction_id       BIGINT PRIMARY KEY,
    gbt_score            DOUBLE NOT NULL,
    transaction_amount   DOUBLE NOT NULL,
    tier                 VARCHAR(10) NOT NULL,
    escalation_reason    VARCHAR(10),
    threshold_config_id  BIGINT,
    assigned_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (threshold_config_id) REFERENCES tier_threshold_config(id)
);

CREATE TABLE IF NOT EXISTS evidence_snapshots (
    transaction_id        BIGINT PRIMARY KEY,
    feature_snapshot_json CLOB NOT NULL,
    gbt_score             DOUBLE NOT NULL,
    tier                  VARCHAR(10) NOT NULL,
    delivery_status       VARCHAR(10) DEFAULT 'PENDING',
    delivery_confirmed_at TIMESTAMP,
    cached_at             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_evidence_cached_at ON evidence_snapshots(cached_at);

CREATE TABLE IF NOT EXISTS dispute_verdicts (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    transaction_id      BIGINT NOT NULL,
    reason_code         VARCHAR(30) NOT NULL,
    verdict             VARCHAR(20) NOT NULL,
    confidence          DOUBLE NOT NULL,
    contradiction_flags CLOB,
    evidence_summary    VARCHAR(1000),
    routing_decision    VARCHAR(20) NOT NULL,
    customer_text       CLOB,
    decided_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_verdicts_transaction ON dispute_verdicts(transaction_id);

