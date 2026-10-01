-- Reference tables
CREATE TABLE stores (
    store_nbr   INT PRIMARY KEY,
    city        TEXT NOT NULL,
    state       TEXT NOT NULL,
    type        CHAR(1) NOT NULL,
    cluster     INT NOT NULL
);

CREATE TABLE holidays (
    id          SERIAL PRIMARY KEY,
    date        DATE NOT NULL,
    type        TEXT NOT NULL,
    locale      TEXT NOT NULL,
    locale_name TEXT NOT NULL,
    description TEXT NOT NULL,
    transferred BOOLEAN NOT NULL
);
CREATE INDEX idx_holidays_date ON holidays(date);

CREATE TABLE oil (
    date        DATE PRIMARY KEY,
    dcoilwtico  NUMERIC(10,2)
);

-- Fact tables
CREATE TABLE sales (
    id          INT PRIMARY KEY,
    date        DATE NOT NULL,
    store_nbr   INT NOT NULL REFERENCES stores(store_nbr),
    family      TEXT NOT NULL,
    sales       NUMERIC(12,3) NOT NULL,
    onpromotion INT NOT NULL
);
CREATE INDEX idx_sales_store_family_date ON sales(store_nbr, family, date);
CREATE INDEX idx_sales_date ON sales(date);

CREATE TABLE transactions (
    date         DATE NOT NULL,
    store_nbr    INT NOT NULL REFERENCES stores(store_nbr),
    transactions INT NOT NULL,
    PRIMARY KEY (date, store_nbr)
);

-- Filled in later phases
CREATE TABLE inventory_snapshots (
    date          DATE NOT NULL,
    store_nbr     INT NOT NULL REFERENCES stores(store_nbr),
    family        TEXT NOT NULL,
    on_hand       NUMERIC(12,3) NOT NULL,
    on_order      NUMERIC(12,3) NOT NULL DEFAULT 0,
    stockout_qty  NUMERIC(12,3) NOT NULL DEFAULT 0,
    PRIMARY KEY (date, store_nbr, family)
);

CREATE TABLE forecasts (
    date          DATE NOT NULL,
    store_nbr     INT NOT NULL REFERENCES stores(store_nbr),
    family        TEXT NOT NULL,
    predicted     NUMERIC(12,3) NOT NULL,
    model_version TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (date, store_nbr, family, model_version)
);

CREATE TABLE reorder_recommendations (
    id             SERIAL PRIMARY KEY,
    run_date       DATE NOT NULL,
    store_nbr      INT NOT NULL REFERENCES stores(store_nbr),
    family         TEXT NOT NULL,
    reorder_point  NUMERIC(12,3) NOT NULL,
    safety_stock   NUMERIC(12,3) NOT NULL,
    order_qty      NUMERIC(12,3) NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('OK','LOW_STOCK','OVERSTOCK','REORDER')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
