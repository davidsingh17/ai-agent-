-- Placeholder per tabelle future (fatture/righe/payments).
docker exec -i ai-agent-db-1 psql -U ai_agent -d ai_agent <<'SQL'
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS invoices (
  id UUID PRIMARY KEY,
  s3_bucket TEXT NOT NULL,
  s3_key TEXT NOT NULL,
  filename TEXT NOT NULL,
  invoice_number TEXT,
  intestatario TEXT,
  partita_iva TEXT,
  codice_fiscale TEXT,
  issue_date DATE,
  due_date DATE,
  currency TEXT,
  imponibile NUMERIC(12,2),
  iva NUMERIC(12,2),
  totale NUMERIC(12,2),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS invoice_lines (
  id UUID PRIMARY KEY,
  invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  line_number INT NOT NULL,
  descrizione TEXT,
  qta NUMERIC(12,3),
  prezzo_unitario NUMERIC(12,2),
  aliquota_iva NUMERIC(5,2),
  totale_riga NUMERIC(12,2)
);

CREATE INDEX IF NOT EXISTS idx_invoices_s3key ON invoices (s3_key);
CREATE INDEX IF NOT EXISTS idx_invoices_piva ON invoices (partita_iva);
CREATE INDEX IF NOT EXISTS idx_invoices_issue_date ON invoices (issue_date);
SQL