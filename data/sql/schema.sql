-- Insurance claims synthetic dataset: schema (SQLite).
-- Parent tables come first. Dates are ISO text; booleans are 0/1.

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY NOT NULL,
    full_name TEXT,
    date_of_birth TEXT,
    email TEXT,
    phone TEXT,
    city TEXT,
    region TEXT,
    customer_since TEXT,
    risk_tier TEXT
);

CREATE TABLE coverages (
    coverage_id TEXT PRIMARY KEY NOT NULL,
    product_code TEXT,
    coverage_type TEXT,
    description TEXT,
    default_limit REAL,
    default_deductible REAL
);

CREATE TABLE adjusters (
    adjuster_id TEXT PRIMARY KEY NOT NULL,
    full_name TEXT,
    seniority TEXT,
    specialty TEXT,
    region TEXT,
    approval_authority REAL,
    hire_date TEXT,
    is_active INTEGER
);

CREATE TABLE policies (
    policy_id TEXT PRIMARY KEY NOT NULL,
    customer_id TEXT,
    product_code TEXT,
    effective_date TEXT,
    expiry_date TEXT,
    status TEXT,
    cancellation_date TEXT,
    lapse_date TEXT,
    annual_premium REAL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);
CREATE INDEX idx_policies_customer_id ON policies(customer_id);

CREATE TABLE policy_coverages (
    policy_coverage_id TEXT PRIMARY KEY NOT NULL,
    policy_id TEXT,
    coverage_id TEXT,
    coverage_limit REAL,
    deductible REAL,
    exclusions TEXT,
    effective_date TEXT,
    expiry_date TEXT,
    FOREIGN KEY (policy_id) REFERENCES policies(policy_id),
    FOREIGN KEY (coverage_id) REFERENCES coverages(coverage_id)
);
CREATE INDEX idx_policy_coverages_policy_id ON policy_coverages(policy_id);
CREATE INDEX idx_policy_coverages_coverage_id ON policy_coverages(coverage_id);

CREATE TABLE incidents (
    incident_id TEXT PRIMARY KEY NOT NULL,
    policy_id TEXT,
    incident_type TEXT,
    incident_date TEXT,
    location_city TEXT,
    description TEXT,
    exclusion_triggered TEXT,
    FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
);
CREATE INDEX idx_incidents_policy_id ON incidents(policy_id);

CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY NOT NULL,
    policy_id TEXT,
    incident_id TEXT,
    coverage_id TEXT,
    claim_type TEXT,
    submitted_date TEXT,
    claimed_amount REAL,
    current_status TEXT,
    reporting_delay_days INTEGER,
    prior_claims_12m INTEGER,
    FOREIGN KEY (policy_id) REFERENCES policies(policy_id),
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id),
    FOREIGN KEY (coverage_id) REFERENCES coverages(coverage_id)
);
CREATE INDEX idx_claims_policy_id ON claims(policy_id);
CREATE INDEX idx_claims_incident_id ON claims(incident_id);
CREATE INDEX idx_claims_coverage_id ON claims(coverage_id);

CREATE TABLE claim_items (
    claim_item_id TEXT PRIMARY KEY NOT NULL,
    claim_id TEXT,
    item_category TEXT,
    description TEXT,
    claimed_amount REAL,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);
CREATE INDEX idx_claim_items_claim_id ON claim_items(claim_id);

CREATE TABLE documents (
    document_id TEXT PRIMARY KEY NOT NULL,
    claim_id TEXT,
    document_type TEXT,
    is_mandatory INTEGER,
    status TEXT,
    requested_date TEXT,
    received_date TEXT,
    file_name TEXT,
    file_size_kb INTEGER,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);
CREATE INDEX idx_documents_claim_id ON documents(claim_id);

CREATE TABLE claim_assignments (
    assignment_id TEXT PRIMARY KEY NOT NULL,
    claim_id TEXT,
    adjuster_id TEXT,
    assignment_role TEXT,
    assigned_date TEXT,
    unassigned_date TEXT,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
    FOREIGN KEY (adjuster_id) REFERENCES adjusters(adjuster_id)
);
CREATE INDEX idx_claim_assignments_claim_id ON claim_assignments(claim_id);
CREATE INDEX idx_claim_assignments_adjuster_id ON claim_assignments(adjuster_id);

CREATE TABLE assessments (
    assessment_id TEXT PRIMARY KEY NOT NULL,
    claim_id TEXT,
    adjuster_id TEXT,
    assessed_date TEXT,
    incident_in_coverage_period INTEGER,
    documents_complete INTEGER,
    duplicate_suspected INTEGER,
    fraud_risk_score INTEGER,
    eligible_amount REAL,
    eligibility_decision TEXT,
    reason_code TEXT,
    reason_text TEXT,
    rule_version TEXT,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
    FOREIGN KEY (adjuster_id) REFERENCES adjusters(adjuster_id)
);
CREATE INDEX idx_assessments_claim_id ON assessments(claim_id);
CREATE INDEX idx_assessments_adjuster_id ON assessments(adjuster_id);

CREATE TABLE reserves (
    reserve_id TEXT PRIMARY KEY NOT NULL,
    claim_id TEXT,
    assessment_id TEXT,
    reserve_type TEXT,
    reserve_amount REAL,
    effective_date TEXT,
    supersedes_reserve_id TEXT,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id),
    FOREIGN KEY (supersedes_reserve_id) REFERENCES reserves(reserve_id)
);
CREATE INDEX idx_reserves_claim_id ON reserves(claim_id);
CREATE INDEX idx_reserves_assessment_id ON reserves(assessment_id);
CREATE INDEX idx_reserves_supersedes_reserve_id ON reserves(supersedes_reserve_id);

CREATE TABLE settlements (
    settlement_id TEXT PRIMARY KEY NOT NULL,
    claim_id TEXT,
    assessment_id TEXT,
    routing_decision TEXT,
    recommended_amount REAL,
    deductible_applied REAL,
    limit_applied REAL,
    approved_amount REAL,
    settlement_status TEXT,
    approver_id TEXT,
    approved_date TEXT,
    paid_date TEXT,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id),
    FOREIGN KEY (approver_id) REFERENCES adjusters(adjuster_id)
);
CREATE INDEX idx_settlements_claim_id ON settlements(claim_id);
CREATE INDEX idx_settlements_assessment_id ON settlements(assessment_id);
CREATE INDEX idx_settlements_approver_id ON settlements(approver_id);

CREATE TABLE status_events (
    event_id TEXT PRIMARY KEY NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    event_type TEXT,
    from_status TEXT,
    to_status TEXT,
    event_ts TEXT,
    actor_type TEXT,
    actor_id TEXT,
    reason_code TEXT
);
