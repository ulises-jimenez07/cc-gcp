-- Run via Cloud SQL Studio or by connecting through the VM:
-- mysql -h <PRIVATE_IP> -u root -p

CREATE DATABASE IF NOT EXISTS app_db;

CREATE USER IF NOT EXISTS 'app_user'@'%' IDENTIFIED BY 'StrongPassword123!';
GRANT ALL PRIVILEGES ON app_db.* TO 'app_user'@'%';
FLUSH PRIVILEGES;

USE app_db;

CREATE TABLE IF NOT EXISTS images (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  filename      VARCHAR(255)  NOT NULL,
  original_name VARCHAR(255)  NOT NULL,
  url           VARCHAR(500)  NOT NULL,
  size          INT           NOT NULL,
  mime_type     VARCHAR(100),
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
