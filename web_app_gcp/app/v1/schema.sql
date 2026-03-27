-- Run this after connecting to MariaDB as root: sudo mysql

CREATE DATABASE IF NOT EXISTS app_db;

CREATE USER IF NOT EXISTS 'app_user'@'localhost' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON app_db.* TO 'app_user'@'localhost';
FLUSH PRIVILEGES;

USE app_db;

CREATE TABLE IF NOT EXISTS images (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  filename     VARCHAR(255)  NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  url          VARCHAR(500)  NOT NULL,
  size         INT           NOT NULL,
  mime_type    VARCHAR(100),
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
