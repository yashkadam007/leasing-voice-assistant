CREATE TABLE IF NOT EXISTS properties (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS units (
    id TEXT PRIMARY KEY,
    property_id TEXT NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    bedrooms INTEGER NOT NULL CHECK (bedrooms >= 0),
    bathrooms REAL NOT NULL CHECK (bathrooms >= 0),
    sqft INTEGER CHECK (sqft IS NULL OR sqft > 0),
    monthly_rent INTEGER NOT NULL CHECK (monthly_rent > 0),
    available_from TEXT,
    view TEXT,
    parking TEXT,
    pet_policy TEXT,
    amenities_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL CHECK (status IN ('available', 'leased')),
    UNIQUE (property_id, label)
);

CREATE TABLE IF NOT EXISTS prospects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    normalized_phone TEXT NOT NULL UNIQUE,
    email TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prospect_interests (
    id TEXT PRIMARY KEY,
    prospect_id TEXT NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    property_id TEXT REFERENCES properties(id) ON DELETE SET NULL,
    unit_id TEXT REFERENCES units(id) ON DELETE SET NULL,
    target_key TEXT NOT NULL,
    source TEXT NOT NULL,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'contacted')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (property_id IS NOT NULL OR unit_id IS NOT NULL),
    UNIQUE (prospect_id, source, target_key)
);

CREATE INDEX IF NOT EXISTS idx_units_property_id ON units(property_id);
CREATE INDEX IF NOT EXISTS idx_prospect_interests_prospect_id
    ON prospect_interests(prospect_id);
