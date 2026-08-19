-- ============================================================
--  HOSTEL MANAGEMENT APP - DATABASE SCHEMA
--  Run these statements once in your cloud MySQL console.
-- ============================================================

-- ---------- MEMBERS (permanent tenants) ----------
CREATE TABLE IF NOT EXISTS members (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    dob             DATE,
    address         TEXT,
    father_name     VARCHAR(150),
    father_mobile   VARCHAR(15),
    mother_name     VARCHAR(150),
    mother_mobile   VARCHAR(15),
    whatsapp        VARCHAR(15),
    photo           LONGTEXT,
    father_pic      LONGTEXT,
    id_front        LONGTEXT,
    id_back         LONGTEXT,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_members_name (name),
    INDEX idx_members_whatsapp (whatsapp),
    INDEX idx_members_status (is_active)
);

-- ---------- ROOMS (19 fixed rooms) ----------
CREATE TABLE IF NOT EXISTS rooms (
    room_no     VARCHAR(5) PRIMARY KEY,
    capacity    INT DEFAULT 3
);

-- ---------- OCCUPANCY (which member is in which room/bed) ----------
CREATE TABLE IF NOT EXISTS occupancy (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    member_id    INT NOT NULL,
    room_no      VARCHAR(5) NOT NULL,
    bed          CHAR(1) NOT NULL,           -- 'A', 'B', or 'C'
    start_date   DATE NOT NULL,
    daily_rent   DECIMAL(10,2) NOT NULL,
    is_active    TINYINT(1) DEFAULT 1,
    FOREIGN KEY (member_id) REFERENCES members(id),
    FOREIGN KEY (room_no) REFERENCES rooms(room_no),
    INDEX idx_occupancy_room (room_no),
    INDEX idx_occupancy_member (member_id),
    INDEX idx_occupancy_status (is_active)
);

-- ---------- RENT HISTORY (each payment made) ----------
CREATE TABLE IF NOT EXISTS rent_history (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    member_id        INT NOT NULL,
    occupancy_id     INT,
    amount_received  DECIMAL(10,2) NOT NULL,
    receiver_name    VARCHAR(150),
    paid_days        DECIMAL(10,2) NOT NULL,
    txn_date         DATE NOT NULL,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES members(id),
    FOREIGN KEY (occupancy_id) REFERENCES occupancy(id),
    INDEX idx_rent_member (member_id)
);

-- ---------- GUESTS (temporary guests) ----------
CREATE TABLE IF NOT EXISTS guests (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(150) NOT NULL,
    whatsapp       VARCHAR(15),
    purpose        VARCHAR(255),
    start_date     DATE,
    leaving_date   DATE,
    total_rent     DECIMAL(10,2) DEFAULT 0,
    advance_given  DECIMAL(10,2) DEFAULT 0,
    room_no        VARCHAR(5),
    photo          LONGTEXT,
    id_front       LONGTEXT,
    id_back        LONGTEXT,
    status         VARCHAR(20) DEFAULT 'active',
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_guests_name (name),
    INDEX idx_guests_status (status)
);

-- ---------- EXPENSES ----------
CREATE TABLE IF NOT EXISTS expenses (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    exp_date     DATE NOT NULL,
    category     VARCHAR(50) NOT NULL,
    amount       DECIMAL(10,2) NOT NULL,
    notes        TEXT,
    created_by   VARCHAR(150),
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_expenses_date (exp_date),
    INDEX idx_expenses_category (category)
);

-- ---------- AUDIT LOG (record of important actions) ----------
CREATE TABLE IF NOT EXISTS audit_log (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    actor        VARCHAR(150),
    action       VARCHAR(100),
    entity       VARCHAR(50),
    entity_id    INT,
    details_json TEXT,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_entity (entity, entity_id)
);

-- ---------- DEPOSITS (security deposit tracking) ----------
CREATE TABLE IF NOT EXISTS deposits (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    member_id       INT,
    guest_id        INT,
    deposit_amount  DECIMAL(10,2) NOT NULL,
    deposit_date    DATE NOT NULL,
    refunded_amount DECIMAL(10,2) DEFAULT 0,
    refund_date     DATE,
    FOREIGN KEY (member_id) REFERENCES members(id),
    FOREIGN KEY (guest_id) REFERENCES guests(id)
);

-- ---------- SEED THE 19 FIXED ROOMS ----------
INSERT IGNORE INTO rooms (room_no, capacity) VALUES
('01',3),('02',3),('03',3),('04',3),('05',3),('06',3),
('11',3),('12',3),('13',3),('14',3),('15',3),
('21',3),('22',3),('23',3),('24',3),
('31',3),('32',3),('33',3),('34',3);