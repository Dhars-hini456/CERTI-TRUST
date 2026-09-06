-- CertiTrust MySQL Schema
-- Import this file in phpMyAdmin (or via `mysql -u root -p certitrust < schema.sql`)
-- after creating an empty database named `certitrust`.
--
-- NOTE: If you run the app with the default DATABASE_URL (sqlite:///certitrust.db)
-- you do NOT need this file at all - SQLAlchemy creates the SQLite tables
-- automatically on first run. Use this file only if you want to run CertiTrust
-- against MySQL via XAMPP.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS fraud_alerts;
DROP TABLE IF EXISTS verification_logs;
DROP TABLE IF EXISTS certificate_versions;
DROP TABLE IF EXISTS certificates;
DROP TABLE IF EXISTS application_documents;
DROP TABLE IF EXISTS applications;
DROP TABLE IF EXISTS certificate_types;
DROP TABLE IF EXISTS departments;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(36) UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(30) NOT NULL,
    department VARCHAR(120),
    phone VARCHAR(20),
    is_active TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE departments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    code VARCHAR(20) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE certificate_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    code VARCHAR(20) NOT NULL UNIQUE,
    department VARCHAR(120),
    validity_days INT DEFAULT 365,
    description VARCHAR(255),
    is_active TINYINT(1) DEFAULT 1
) ENGINE=InnoDB;

CREATE TABLE applications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    application_number VARCHAR(40) NOT NULL UNIQUE,
    citizen_id INT NOT NULL,
    certificate_type_id INT,
    applicant_name VARCHAR(150) NOT NULL,
    date_of_birth VARCHAR(20),
    address VARCHAR(255),
    purpose VARCHAR(255),
    status VARCHAR(30) DEFAULT 'SUBMITTED',
    assigned_officer_id INT,
    rejection_reason VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (citizen_id) REFERENCES users(id),
    FOREIGN KEY (certificate_type_id) REFERENCES certificate_types(id),
    FOREIGN KEY (assigned_officer_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE application_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    application_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    stored_path VARCHAR(400) NOT NULL,
    document_type VARCHAR(80),
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id) REFERENCES applications(id)
) ENGINE=InnoDB;

CREATE TABLE certificates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    certificate_number VARCHAR(60) NOT NULL UNIQUE,
    certificate_type_id INT,
    application_id INT,
    department VARCHAR(120),
    applicant_name VARCHAR(150) NOT NULL,
    applicant_id VARCHAR(60),
    date_of_birth VARCHAR(20),
    address VARCHAR(255),
    issue_date VARCHAR(20),
    expiry_date VARCHAR(20),
    issued_by VARCHAR(150),
    officer_id INT,
    status VARCHAR(30) DEFAULT 'ACTIVE',
    version_number INT DEFAULT 1,
    original_certificate_id INT,
    reissue_reason VARCHAR(255),
    document_hash VARCHAR(128) NOT NULL,
    digital_signature TEXT NOT NULL,
    qr_token VARCHAR(64) NOT NULL UNIQUE,
    is_demo_data TINYINT(1) DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (certificate_type_id) REFERENCES certificate_types(id),
    FOREIGN KEY (application_id) REFERENCES applications(id),
    FOREIGN KEY (officer_id) REFERENCES users(id),
    FOREIGN KEY (original_certificate_id) REFERENCES certificates(id)
) ENGINE=InnoDB;

CREATE TABLE certificate_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    certificate_id INT NOT NULL,
    original_certificate_id INT NOT NULL,
    version_number INT NOT NULL,
    reissue_reason VARCHAR(255),
    previous_certificate_hash VARCHAR(128),
    new_certificate_hash VARCHAR(128),
    reissued_by INT,
    reissued_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (certificate_id) REFERENCES certificates(id),
    FOREIGN KEY (original_certificate_id) REFERENCES certificates(id),
    FOREIGN KEY (reissued_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE verification_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    certificate_id INT,
    verifier_id INT,
    verification_method VARCHAR(30),
    verification_result VARCHAR(40),
    ip_address VARCHAR(60),
    user_agent VARCHAR(255),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (certificate_id) REFERENCES certificates(id),
    FOREIGN KEY (verifier_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE fraud_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    certificate_id INT,
    alert_type VARCHAR(60) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    reason VARCHAR(255),
    detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved TINYINT(1) DEFAULT 0,
    resolved_by INT,
    FOREIGN KEY (certificate_id) REFERENCES certificates(id),
    FOREIGN KEY (resolved_by) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    message VARCHAR(400),
    is_read TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(150) NOT NULL,
    details VARCHAR(400),
    ip_address VARCHAR(60),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS = 1;
