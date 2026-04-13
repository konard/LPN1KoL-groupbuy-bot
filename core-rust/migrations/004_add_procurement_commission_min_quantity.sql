-- Add commission_percent and min_quantity columns to procurements table
-- Mirrors Django migration 0002_procurement_commission_min_quantity_suppliervote

ALTER TABLE procurements
    ADD COLUMN IF NOT EXISTS commission_percent DECIMAL(4, 2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS min_quantity DECIMAL(10, 2);
