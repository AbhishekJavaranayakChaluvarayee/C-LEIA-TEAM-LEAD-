-- Enhanced schema for C-LEIA system
DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS student_sessions;
DROP TABLE IF EXISTS personas;
DROP TABLE IF EXISTS domains;

-- Domains table (you have this)
CREATE TABLE domains (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Personas table (enhanced)
CREATE TABLE personas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    domain_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL, -- e.g., "Theater Owner", "Operations Manager"
    background_story TEXT NOT NULL,
    initial_prompt TEXT NOT NULL,
    personality_traits TEXT, -- Additional personality details
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE
);

-- Student sessions for tracking individual student work
CREATE TABLE student_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    student_id VARCHAR(255), -- Could be anonymous or linked to auth system
    domain_id INT NOT NULL,
    persona_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (domain_id) REFERENCES domains(id),
    FOREIGN KEY (persona_id) REFERENCES personas(id)
);

-- Conversations table (enhanced)
CREATE TABLE conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    persona_id INT NOT NULL,
    sender ENUM('student', 'persona') NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES student_sessions(session_id),
    FOREIGN KEY (persona_id) REFERENCES personas(id),
    INDEX idx_session_created (session_id, created_at)
);

-- Solutions/outputs submitted by students
CREATE TABLE student_solutions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    solution_type ENUM('mermaid_diagram', 'requirements_list', 'user_stories', 'other') NOT NULL,
    solution_content TEXT NOT NULL,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES student_sessions(session_id)
);

-- Evaluation/feedback data
CREATE TABLE session_evaluations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    evaluation_criteria JSON, -- Store structured evaluation data
    score DECIMAL(5,2),
    feedback TEXT,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES student_sessions(session_id)
);

-- Insert theater domain from the PDF example
-- INSERT INTO domains (name, description) VALUES
-- ('Online Ticket Platform', 'Requirements gathering for an online theater ticket booking platform with multiple venues, shows, and complex seating arrangements.');

-- -- Get the domain ID
-- SET @domain_id = LAST_INSERT_ID();

-- -- Insert the theater owner persona from the PDF
-- INSERT INTO personas (domain_id, name, role, background_story, initial_prompt, personality_traits) VALUES
-- (@domain_id, 
--  'Ethan Thompson', 
--  'Theater Owner',
--  'You own a company that operates multiple theaters in San Francisco. You want an online ticket platform to make ticket purchasing more efficient and increase sales. You have operations and marketing teams that will use the system.',
--  'You are Ethan Thompson, theater owner. Your main concerns are efficiency, user-friendliness, and increasing sales. You want minimal manual work from your team. Be specific about your business needs but let the student discover requirements through questioning.',
--  'Business-focused, practical, willing to compromise on nice-to-have features if core functionality works well. You understand your business but need help translating needs into technical requirements.'
-- );