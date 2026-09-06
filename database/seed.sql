-- CertiTrust demo seed data (reference tables only).
--
-- Certificates require a runtime-generated SHA-256 hash, RSA digital
-- signature and QR code image, so citizens, officers, applications and
-- certificates are seeded by the Python script `scripts/seed_data.py`
-- instead of plain SQL (run: python scripts/seed_data.py).
--
-- This file only seeds the static reference data: departments and
-- certificate types. Run this AFTER schema.sql if you are using MySQL.

INSERT INTO departments (name, code, description) VALUES
('Revenue Department', 'REV', 'Handles income, caste and nativity certificates'),
('Registrar of Births & Deaths', 'RBD', 'Handles birth and death certificates'),
('Social Welfare Department', 'SWD', 'Handles disability and legal heir certificates'),
('General Administration Department', 'GAD', 'Handles residence and miscellaneous certificates');

INSERT INTO certificate_types (name, code, department, validity_days, description, is_active) VALUES
('Caste / Community Certificate', 'CAS', 'Revenue Department', 1825, 'Certifies community/caste for reservation benefits', 1),
('Income Certificate', 'INC', 'Revenue Department', 365, 'Certifies annual family income', 1),
('Nativity Certificate', 'NAT', 'Revenue Department', 3650, 'Certifies native residency status', 1),
('Residence Certificate', 'RES', 'General Administration Department', 1825, 'Certifies current residential address', 1),
('Birth Certificate', 'BIR', 'Registrar of Births & Deaths', 36500, 'Certifies date and place of birth', 1),
('Death Certificate', 'DEA', 'Registrar of Births & Deaths', 36500, 'Certifies date and cause of death', 1),
('Legal Heir Certificate', 'LEG', 'Social Welfare Department', 3650, 'Certifies legal heirs of a deceased person', 1),
('Disability Certificate', 'DIS', 'Social Welfare Department', 1825, 'Certifies percentage and type of disability', 1);
