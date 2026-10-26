CREATE DATABASE IF NOT EXISTS campuscrew
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE campuscrew;

CREATE TABLE IF NOT EXISTS clubs (
    club_id INT AUTO_INCREMENT PRIMARY KEY,
    club_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS volunteers (
    volunteer_id INT AUTO_INCREMENT PRIMARY KEY,
    roll_no VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120),
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memberships (
    volunteer_id INT NOT NULL,
    club_id INT NOT NULL,
    PRIMARY KEY (volunteer_id, club_id),
    FOREIGN KEY (volunteer_id) REFERENCES volunteers(volunteer_id)
      ON DELETE CASCADE,
    FOREIGN KEY (club_id) REFERENCES clubs(club_id)
      ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    club_id INT NOT NULL,
    event_name VARCHAR(150) NOT NULL,
    event_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    venue VARCHAR(150) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (club_id) REFERENCES clubs(club_id),
    CONSTRAINT chk_event_time CHECK (end_time > start_time)
);

CREATE TABLE IF NOT EXISTS roles (
    role_id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    role_name ENUM('Tech Volunteer','Art Volunteer','PR and Management Volunteer') NOT NULL,
    required_count INT NOT NULL DEFAULT 1,
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE,
    UNIQUE (event_id, role_name),
    CONSTRAINT chk_required_count CHECK (required_count > 0)
);

CREATE TABLE IF NOT EXISTS assignments (
    assignment_id INT AUTO_INCREMENT PRIMARY KEY,
    role_id INT NOT NULL,
    volunteer_id INT NOT NULL,
    attendance ENUM('Not Marked','Present','Absent') NOT NULL DEFAULT 'Not Marked',
    hours_worked DECIMAL(5,2) NOT NULL DEFAULT 0,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(role_id) ON DELETE CASCADE,
    FOREIGN KEY (volunteer_id) REFERENCES volunteers(volunteer_id) ON DELETE CASCADE,
    UNIQUE (role_id, volunteer_id),
    CONSTRAINT chk_hours CHECK (hours_worked >= 0)
);

INSERT IGNORE INTO clubs (club_name) VALUES
('Trendles'),
('Wildbeats'),
('GDG'),
('Coders Club'),
('BetaLabs'),
('Cybersecurity Club'),
('Enigma'),
('Elix');
