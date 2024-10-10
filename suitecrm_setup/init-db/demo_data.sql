-- -----------------------------------------------------
-- SuiteCRM Demo Data Import Script
-- Inserts 10 records each for Accounts, Contacts, Leads, Opportunities, Cases, and Users
-- -----------------------------------------------------

USE bitnami_suitecrm;
-- Disable foreign key checks to avoid constraint issues during import
SET FOREIGN_KEY_CHECKS = 0;

-- -----------------------------------------------------
-- Insert Users
-- -----------------------------------------------------
INSERT INTO users (id, user_name, first_name, last_name, date_entered, date_modified, is_admin, status)
VALUES
(UUID(), 'jdoe', 'John', 'Doe', NOW(), NOW(), 0, 1),
(UUID(), 'asmith', 'Alice', 'Smith', NOW(), NOW(), 0, 1),
(UUID(), 'bjones', 'Bob', 'Jones', NOW(), NOW(), 0, 1),
(UUID(), 'cjames', 'Carol', 'James', NOW(), NOW(), 0, 1),
(UUID(), 'dwilson', 'David', 'Wilson', NOW(), NOW(), 0, 1),
(UUID(), 'emiller', 'Emma', 'Miller', NOW(), NOW(), 0, 1),
(UUID(), 'fgarcia', 'Frank', 'Garcia', NOW(), NOW(), 0, 1),
(UUID(), 'gharris', 'Grace', 'Harris', NOW(), NOW(), 0, 1),
(UUID(), 'hlee', 'Henry', 'Lee', NOW(), NOW(), 0, 1);

-- -----------------------------------------------------
-- Insert Accounts
-- -----------------------------------------------------
INSERT INTO accounts (id, name, billing_address_street, billing_address_city, billing_address_state, billing_address_postalcode, billing_address_country, date_entered, date_modified, assigned_user_id) VALUES
(UUID(), 'Acme Corporation', '123 Elm Street', 'Metropolis', 'NY', '10001', 'USA', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'jdoe')),
(UUID(), 'Globex Industries', '456 Oak Avenue', 'Gotham', 'IL', '60601', 'USA', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'asmith')),
(UUID(), 'Soylent Corp', '789 Pine Road', 'Star City', 'CA', '90001', 'USA', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'bjones')),
(UUID(), 'Initech', '321 Maple Lane', 'Central City', 'TX', '73301', 'USA', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'cjames')),
(UUID(), 'Umbrella Corporation', '654 Cedar Blvd', 'Coast City', 'FL', '33101', 'USA', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'dwilson')),
(UUID(), 'Massive Dynamic', '135 Spruce Drive', 'Smallville', 'OR', '97035', 'USA', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'emiller')),
(UUID(), 'Stark Industries', '246 Aspen Court', 'Atlantis', 'NJ', '07001', 'USA', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'fharris')),
(UUID(), 'Wayne Enterprises', '579 Willow Way', 'National City', 'NV', '18901', 'USA', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'hlee')),
(UUID(), 'Wonka Industries', '864 Poplar Place', 'Emerald City', 'CO', '80014', 'USA', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'hlee'));


-- -----------------------------------------------------
-- Insert Contacts
-- -----------------------------------------------------
INSERT INTO contacts (id, first_name, last_name, phone_work, date_entered, date_modified, assigned_user_id)
VALUES
(UUID(), 'Michael', 'Scott', '555-0100', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'jdoe')),
(UUID(), 'Pam', 'Beesly', '555-0101', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'jdoe')),
(UUID(), 'Jim', 'Halpert', '555-0102', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'asmith')),
(UUID(), 'Dwight', 'Schrute', '555-0103', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'bjones')),
(UUID(), 'Angela', 'Martin', '555-0104', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'cjames')),
(UUID(), 'Oscar', 'Martinez', '555-0105', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'dwilson')),
(UUID(), 'Kevin', 'Malone', '555-0106', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'emiller')),
(UUID(), 'Stanley', 'Hudson', '555-0107', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'fgarcia')),
(UUID(), 'Ryan', 'Howard', '555-0108', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'gharris')),
(UUID(), 'Toby', 'Flenderson', '555-0109', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'hlee'));

-- -----------------------------------------------------
-- Insert Email Addresses
-- -----------------------------------------------------
INSERT INTO email_addresses (id, email_address, email_address_caps, invalid_email, opt_out, date_created, date_modified)
VALUES
(UUID(), 'michael.scott@dundermifflin.com', 'MICHAEL.SCOTT@DUNDERMIFFLIN.COM', 0, 0, NOW(), NOW()),
(UUID(), 'pam.beesly@dundermifflin.com', 'PAM.BEESLY@DUNDERMIFFLIN.COM', 0, 0, NOW(), NOW()),
(UUID(), 'jim.halpert@dundermifflin.com', 'JIM.HALPERT@DUNDERMIFFLIN.COM', 0, 0, NOW(), NOW()),
(UUID(), 'dwight.schrute@dundermifflin.com', 'DWIGHT.SCHRUTE@DUNDERMIFFLIN.COM', 0, 0, NOW(), NOW()),
(UUID(), 'angela.martin@dundermifflin.com', 'ANGELA.MARTIN@DUNDERMIFFLIN.COM', 0, 0, NOW(), NOW()),
(UUID(), 'oscar.martinez@dundermifflin.com', 'OSCAR.MARTINEZ@DUNDERMIFFLIN.COM', 0, 0, NOW(), NOW()),
(UUID(), 'kevin.malone@dundermifflin.com', 'KEVIN.MALONE@DUNDERMIFFLIN.COM', 0, 0, NOW(), NOW()),
(UUID(), 'stanley.hudson@dundermifflin.com', 'STANLEY.HUDSON@DUNDERMIFFLIN.COM', 0, 0, NOW(), NOW()),
(UUID(), 'ryan.howard@dundermifflin.com', 'RYAN.HOWARD@DUNDERMIFFLIN.COM', 0, 0, NOW(), NOW()),
(UUID(), 'toby.flenderson@dundermifflin.com', 'TOBY.FLENDERSON@DUNDERMIFFLIN.COM', 0, 0, NOW(), NOW());

-- -----------------------------------------------------
-- Link Email Addresses to Contacts
-- -----------------------------------------------------
INSERT INTO email_addr_bean_rel (id, email_address_id, bean_id, bean_module, primary_address, reply_to_address, date_created, date_modified, deleted)
VALUES
(UUID(), (SELECT id FROM email_addresses WHERE email_address = 'michael.scott@dundermifflin.com'), (SELECT id FROM contacts WHERE first_name = 'Michael' AND last_name = 'Scott'), 'Contacts', 1, 0, NOW(), NOW(), 0),
(UUID(), (SELECT id FROM email_addresses WHERE email_address = 'pam.beesly@dundermifflin.com'), (SELECT id FROM contacts WHERE first_name = 'Pam' AND last_name = 'Beesly'), 'Contacts', 1, 0, NOW(), NOW(), 0),
(UUID(), (SELECT id FROM email_addresses WHERE email_address = 'jim.halpert@dundermifflin.com'), (SELECT id FROM contacts WHERE first_name = 'Jim' AND last_name = 'Halpert'), 'Contacts', 1, 0, NOW(), NOW(), 0),
(UUID(), (SELECT id FROM email_addresses WHERE email_address = 'dwight.schrute@dundermifflin.com'), (SELECT id FROM contacts WHERE first_name = 'Dwight' AND last_name = 'Schrute'), 'Contacts', 1, 0, NOW(), NOW(), 0),
(UUID(), (SELECT id FROM email_addresses WHERE email_address = 'angela.martin@dundermifflin.com'), (SELECT id FROM contacts WHERE first_name = 'Angela' AND last_name = 'Martin'), 'Contacts', 1, 0, NOW(), NOW(), 0),
(UUID(), (SELECT id FROM email_addresses WHERE email_address = 'oscar.martinez@dundermifflin.com'), (SELECT id FROM contacts WHERE first_name = 'Oscar' AND last_name = 'Martinez'), 'Contacts', 1, 0, NOW(), NOW(), 0),
(UUID(), (SELECT id FROM email_addresses WHERE email_address = 'kevin.malone@dundermifflin.com'), (SELECT id FROM contacts WHERE first_name = 'Kevin' AND last_name = 'Malone'), 'Contacts', 1, 0, NOW(), NOW(), 0),
(UUID(), (SELECT id FROM email_addresses WHERE email_address = 'stanley.hudson@dundermifflin.com'), (SELECT id FROM contacts WHERE first_name = 'Stanley' AND last_name = 'Hudson'), 'Contacts', 1, 0, NOW(), NOW(), 0),
(UUID(), (SELECT id FROM email_addresses WHERE email_address = 'ryan.howard@dundermifflin.com'), (SELECT id FROM contacts WHERE first_name = 'Ryan' AND last_name = 'Howard'), 'Contacts', 1, 0, NOW(), NOW(), 0),
(UUID(), (SELECT id FROM email_addresses WHERE email_address = 'toby.flenderson@dundermifflin.com'), (SELECT id FROM contacts WHERE first_name = 'Toby' AND last_name = 'Flenderson'), 'Contacts', 1, 0, NOW(), NOW(), 0);



-- -----------------------------------------------------
-- Insert Leads
-- -----------------------------------------------------
INSERT INTO leads (id, first_name, last_name, phone_mobile, status, date_entered, date_modified, assigned_user_id)
VALUES
(UUID(), 'Bruce', 'Wayne', '555-0200', 'New', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'jdoe')),
(UUID(), 'Clark', 'Kent', '555-0201', 'Assigned', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'asmith')),
(UUID(), 'Diana', 'Prince', '555-0202', 'In Process', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'bjones')),
(UUID(), 'Barry', 'Allen', '555-0203', 'Converted', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'cjames')),
(UUID(), 'Hal', 'Jordan', '555-0204', 'Dead', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'dwilson')),
(UUID(), 'Arthur', 'Curry', '555-0205', 'New', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'emiller')),
(UUID(), 'Victor', 'Stone', '555-0206', 'Assigned', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'fgarcia')),
(UUID(), 'Peter', 'Parker', '555-0207', 'In Process', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'gharris')),
(UUID(), 'Tony', 'Stark', '555-0208', 'Converted', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'hlee')),
(UUID(), 'Natasha', 'Romanoff', '555-0209', 'Dead', NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'hlee'));

-- Insert Email Addresses for Leads
INSERT INTO email_addresses (id, email_address, email_address_caps, invalid_email, opt_out, date_created, date_modified)
VALUES
(UUID(), 'bruce.wayne@wayneenterprises.com', 'BRUCE.WAYNE@WAYNEENTERPRISES.COM', 0, 0, NOW(), NOW()),
(UUID(), 'clark.kent@dailyplanet.com', 'CLARK.KENT@DAILYPALANT.COM', 0, 0, NOW(), NOW()),
(UUID(), 'diana.prince@themiscira.com', 'DIANA.PRINCE@THEMISCIRA.COM', 0, 0, NOW(), NOW()),
(UUID(), 'barry.allen@ccpd.com', 'BARRY.ALLEN@CCPD.COM', 0, 0, NOW(), NOW()),
(UUID(), 'hal.jordan@galaxy.com', 'HAL.JORDAN@GALAXY.COM', 0, 0, NOW(), NOW()),
(UUID(), 'arthur.curry@atlantis.com', 'ARTHUR.CURRY@ATLANTIS.COM', 0, 0, NOW(), NOW()),
(UUID(), 'victor.stone@starkindustries.com', 'VICTOR.STONE@STARKINDUSTRIES.COM', 0, 0, NOW(), NOW()),
(UUID(), 'peter.parker@dailybugle.com', 'PETER.PARKER@DAILYBUGLE.COM', 0, 0, NOW(), NOW()),
(UUID(), 'tony.stark@starkindustries.com', 'TONY.STARK@STARKINDUSTRIES.COM', 0, 0, NOW(), NOW()),
(UUID(), 'natasha.romanoff@shield.com', 'NATASHA.ROMANOFF@SHIELD.COM', 0, 0, NOW(), NOW());

-- -----------------------------------------------------
-- Insert Opportunities
-- -----------------------------------------------------
INSERT INTO opportunities (id, name, amount, sales_stage, probability, date_closed, date_entered, date_modified, assigned_user_id)
VALUES
(UUID(), 'Website Redesign', 50000, 'Prospecting', 10, DATE_ADD(NOW(), INTERVAL 30 DAY), NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'jdoe')),
(UUID(), 'Mobile App Development', 75000, 'Proposal/Price Quote', 25, DATE_ADD(NOW(), INTERVAL 45 DAY), NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'asmith')),
(UUID(), 'Cloud Migration', 120000, 'Negotiation/Review', 50, DATE_ADD(NOW(), INTERVAL 60 DAY), NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'bjones')),
(UUID(), 'Cybersecurity Upgrade', 200000, 'Closed Won', 100, DATE_ADD(NOW(), INTERVAL -10 DAY), NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'cjames')),
(UUID(), 'Data Analytics Implementation', 150000, 'Closed Lost', 0, DATE_ADD(NOW(), INTERVAL -20 DAY), NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'dwilson')),
(UUID(), 'AI Integration', 300000, 'Prospecting', 15, DATE_ADD(NOW(), INTERVAL 90 DAY), NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'emiller')),
(UUID(), 'ERP Deployment', 500000, 'Proposal/Price Quote', 30, DATE_ADD(NOW(), INTERVAL 120 DAY), NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'fgarcia')),
(UUID(), 'Marketing Automation', 80000, 'Negotiation/Review', 60, DATE_ADD(NOW(), INTERVAL 75 DAY), NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'gharris')),
(UUID(), 'Customer Portal Setup', 65000, 'Closed Won', 100, DATE_ADD(NOW(), INTERVAL -5 DAY), NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'hlee')),
(UUID(), 'Inventory Management', 90000, 'Closed Lost', 0, DATE_ADD(NOW(), INTERVAL -15 DAY), NOW(), NOW(), (SELECT id FROM users WHERE user_name = 'hlee'));


---- Relation

INSERT INTO accounts_opportunities (id, account_id, opportunity_id, date_modified, deleted)
VALUES
(UUID(), 
 (SELECT id FROM accounts WHERE name = 'Acme Corporation'), 
 (SELECT id FROM opportunities WHERE name = 'Website Redesign'), 
 NOW(), 0),
(UUID(), 
 (SELECT id FROM accounts WHERE name = 'Globex Industries'), 
 (SELECT id FROM opportunities WHERE name = 'Mobile App Development'), 
 NOW(), 0),
(UUID(), 
 (SELECT id FROM accounts WHERE name = 'Soylent Corp'), 
 (SELECT id FROM opportunities WHERE name = 'Cloud Migration'), 
 NOW(), 0),
(UUID(), 
 (SELECT id FROM accounts WHERE name = 'Initech'), 
 (SELECT id FROM opportunities WHERE name = 'Cybersecurity Upgrade'), 
 NOW(), 0),
(UUID(), 
 (SELECT id FROM accounts WHERE name = 'Umbrella Corporation'), 
 (SELECT id FROM opportunities WHERE name = 'Data Analytics Implementation'), 
 NOW(), 0),
(UUID(), 
 (SELECT id FROM accounts WHERE name = 'Hooli'), 
 (SELECT id FROM opportunities WHERE name = 'AI Integration'), 
 NOW(), 0),
(UUID(), 
 (SELECT id FROM accounts WHERE name = 'Massive Dynamic'), 
 (SELECT id FROM opportunities WHERE name = 'ERP Deployment'), 
 NOW(), 0),
(UUID(), 
 (SELECT id FROM accounts WHERE name = 'Stark Industries'), 
 (SELECT id FROM opportunities WHERE name = 'Marketing Automation'), 
 NOW(), 0),
(UUID(), 
 (SELECT id FROM accounts WHERE name = 'Wayne Enterprises'), 
 (SELECT id FROM opportunities WHERE name = 'Customer Portal Setup'), 
 NOW(), 0),
(UUID(), 
 (SELECT id FROM accounts WHERE name = 'Wonka Industries'), 
 (SELECT id FROM opportunities WHERE name = 'Inventory Management'), 
 NOW(), 0);


-- Re-enable foreign key checks after import
SET FOREIGN_KEY_CHECKS = 1;

-- -----------------------------------------------------
-- End of Demo Data Import Script
-- -----------------------------------------------------
