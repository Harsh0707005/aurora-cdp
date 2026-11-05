-- V7: Customer Attributes (behavioural feature store keyed by id; internals §4.2) and per-destination Activation IDs (§4.4).
CREATE TABLE IF NOT EXISTS customer_attributes (
    aurora_id                        VARCHAR(36) NOT NULL,
    run_id                           VARCHAR(64) NOT NULL,
    as_of                            DATE        NOT NULL,
    first_order_brand VARCHAR, first_order_channel VARCHAR, first_order_store_id VARCHAR, first_order_id VARCHAR, first_order_date DATE,
    first_order_net_amt DOUBLE, first_order_total_amt DOUBLE, first_order_total_items BIGINT,
    second_order_brand VARCHAR, second_order_channel VARCHAR, second_order_store_id VARCHAR, second_order_id VARCHAR, second_order_date DATE,
    second_order_net_amt DOUBLE, second_order_total_amt DOUBLE, second_order_total_items BIGINT,
    latest_order_brand VARCHAR, latest_order_channel VARCHAR, latest_order_store_id VARCHAR, latest_order_id VARCHAR, latest_order_date DATE,
    latest_order_net_amt DOUBLE, latest_order_total_amt DOUBLE, latest_order_total_items BIGINT,
    first_to_second_order_days BIGINT, first_to_latest_order_days BIGINT, days_since_latest_order BIGINT,
    one_and_done VARCHAR(1), single_brand VARCHAR(1), multi_brand VARCHAR(1), single_channel VARCHAR(1), multi_channel VARCHAR(1),
    early_repeat_purchaser VARCHAR(1), retail_flag VARCHAR(1),
    lifetime_brands VARCHAR, lifetime_preferred_brand VARCHAR, lifetime_channels VARCHAR, lifetime_preferred_channel VARCHAR,
    lifetime_stores VARCHAR, lifetime_preferred_store_id VARCHAR, lifetime_order_net_amt DOUBLE, lifetime_order_total_amt DOUBLE,
    lifetime_order_frequency BIGINT, lifetime_order_total_items BIGINT, lifetime_largest_order_value_amt DOUBLE,
    lifetime_average_order_value_amt DOUBLE, lifetime_average_item_price DOUBLE, lifetime_average_num_items BIGINT,
    l12m_brands VARCHAR, l12m_preferred_brand VARCHAR, l12m_channels VARCHAR, l12m_preferred_channel VARCHAR, l12m_stores VARCHAR,
    l12m_preferred_store_id VARCHAR, l12m_order_net_amt DOUBLE, l12m_order_total_amt DOUBLE, l12m_order_frequency BIGINT,
    l12m_total_items BIGINT, l12m_average_order_value_amt DOUBLE, l12m_average_item_price DOUBLE, l12m_average_num_items BIGINT,
    l6m_brands VARCHAR, l6m_preferred_brand VARCHAR, l6m_channels VARCHAR, l6m_preferred_channel VARCHAR, l6m_stores VARCHAR,
    l6m_preferred_store_id VARCHAR, l6m_order_net_amt DOUBLE, l6m_order_total_amt DOUBLE, l6m_order_frequency BIGINT,
    l6m_total_items BIGINT, l6m_average_order_value_amt DOUBLE, l6m_average_item_price DOUBLE, l6m_average_num_items BIGINT,
    l3m_brands VARCHAR, l3m_preferred_brand VARCHAR, l3m_channels VARCHAR, l3m_preferred_channel VARCHAR, l3m_stores VARCHAR,
    l3m_preferred_store_id VARCHAR, l3m_order_net_amt DOUBLE, l3m_order_total_amt DOUBLE, l3m_order_frequency BIGINT,
    l3m_total_items BIGINT, l3m_average_order_value_amt DOUBLE, l3m_average_item_price DOUBLE, l3m_average_num_items BIGINT,
    l30d_brands VARCHAR, l30d_preferred_brand VARCHAR, l30d_channels VARCHAR, l30d_preferred_channel VARCHAR, l30d_stores VARCHAR,
    l30d_preferred_store_id VARCHAR, l30d_order_net_amt DOUBLE, l30d_order_total_amt DOUBLE, l30d_order_frequency BIGINT,
    l30d_total_items BIGINT, l30d_average_order_value_amt DOUBLE, l30d_average_item_price DOUBLE, l30d_average_num_items BIGINT,
    l12m_recency VARCHAR(1), l12m_frequency VARCHAR(1), l12m_monetary VARCHAR(1), l12m_rfm_score INTEGER, l12m_rfm_customer_segment VARCHAR,
    built_at                         TIMESTAMP   NOT NULL
);

CREATE TABLE IF NOT EXISTS activation_ids (            -- [AMP: Activation IDs] per-destination identifiers insulated from id churn
    destination_id  VARCHAR(128) NOT NULL,
    aurora_id       VARCHAR(36)  NOT NULL,
    activation_id   VARCHAR(36)  NOT NULL,
    first_seen      TIMESTAMP    NOT NULL,
    last_seen       TIMESTAMP    NOT NULL,
    inherited_from  VARCHAR(36),                        -- previous aurora_id whose activation id this one took over on a merge
    PRIMARY KEY (destination_id, aurora_id)
);
