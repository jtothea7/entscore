"""
SQLite database initialization, WAL mode, and migration system
"""
import sqlite3
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from core.logger import setup_logger

logger = setup_logger(__name__)

DB_PATH = "data/entscore.db"

SCHEMA_SQL = """
-- Enable WAL mode for better concurrency
PRAGMA journal_mode=WAL;

-- Schema version tracking for migrations
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Projects (auto-created from domain)
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_domain ON projects(domain);

-- Analyses (one per URL + keyword combination)
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    keyword TEXT NOT NULL,
    health_score REAL,
    entity_coverage_score REAL,
    heading_score REAL,
    word_count_score REAL,
    readability_score REAL,
    link_score REAL,
    client_word_count INTEGER,
    competitor_avg_word_count REAL,
    recommended_word_count_min INTEGER,
    recommended_word_count_max INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analysis_duration_seconds REAL,
    competitors_analyzed INTEGER,
    competitors_failed INTEGER,
    extra_data TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analyses_project ON analyses(project_id);
CREATE INDEX IF NOT EXISTS idx_analyses_url_keyword ON analyses(url, keyword);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at DESC);

-- Competitors (one row per competitor per analysis)
CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    position INTEGER,
    word_count INTEGER,
    heading_count INTEGER,
    entity_count INTEGER,
    scrape_success BOOLEAN,
    scrape_method TEXT,
    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_competitors_analysis ON competitors(analysis_id);

-- Entities (one row per unique entity per analysis)
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    entity_text TEXT NOT NULL,
    entity_type TEXT,
    client_count INTEGER DEFAULT 0,
    client_salience REAL DEFAULT 0.0,
    competitor_frequency INTEGER DEFAULT 0,
    competitor_avg_salience REAL DEFAULT 0.0,
    gap_status TEXT,
    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entities_analysis ON entities(analysis_id);
CREATE INDEX IF NOT EXISTS idx_entities_gap_status ON entities(gap_status);

-- GSC data (uploaded CSV data)
CREATE TABLE IF NOT EXISTS gsc_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL DEFAULT 'queries',
    url TEXT NOT NULL DEFAULT '',
    keyword TEXT NOT NULL DEFAULT '',
    clicks INTEGER,
    impressions INTEGER,
    ctr REAL,
    position REAL,
    opportunity_score REAL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gsc_url ON gsc_data(url);
CREATE INDEX IF NOT EXISTS idx_gsc_source ON gsc_data(source_type);
CREATE INDEX IF NOT EXISTS idx_gsc_opportunity ON gsc_data(opportunity_score DESC);

-- API usage tracking (cost per call)
CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER,
    endpoint TEXT NOT NULL,
    cost REAL NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_api_usage_analysis ON api_usage(analysis_id);

-- Cache tables
CREATE TABLE IF NOT EXISTS api_cache (
    cache_key TEXT PRIMARY KEY,
    response_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_api_cache_expires ON api_cache(expires_at);

CREATE TABLE IF NOT EXISTS scrape_cache (
    url TEXT PRIMARY KEY,
    html TEXT NOT NULL,
    clean_text TEXT NOT NULL,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scrape_cache_expires ON scrape_cache(expires_at);
"""

CURRENT_SCHEMA_VERSION = 2


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and foreign keys enabled."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: str = DB_PATH):
    """Initialize database schema and run migrations."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)

        # Set initial schema version if not exists
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        if row[0] is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (CURRENT_SCHEMA_VERSION,))

        conn.commit()

        # Run any pending migrations for existing databases
        run_migrations(conn)

        logger.info(f"Database initialized at {db_path}")
    finally:
        conn.close()


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get current schema version."""
    try:
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        return row[0] if row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def run_migrations(conn: sqlite3.Connection):
    """Run any pending migrations."""
    current_version = get_schema_version(conn)

    def migrate_v2(conn):
        """Add source_type column to gsc_data and index."""
        try:
            conn.execute("ALTER TABLE gsc_data ADD COLUMN source_type TEXT NOT NULL DEFAULT 'queries'")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_gsc_source ON gsc_data(source_type)")
        except sqlite3.OperationalError:
            pass  # Column already exists (fresh install)

    migrations = {
        2: migrate_v2,
    }

    for version in sorted(migrations.keys()):
        if version > current_version:
            logger.info(f"Running migration to version {version}")
            migrations[version](conn)
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            conn.commit()
            logger.info(f"Migration to version {version} complete")


# --- CRUD Operations ---

def get_or_create_project(conn: sqlite3.Connection, domain: str) -> int:
    """Get existing project by domain or create new one. Returns project_id."""
    cursor = conn.execute("SELECT id FROM projects WHERE domain = ?", (domain,))
    row = cursor.fetchone()
    if row:
        conn.execute(
            "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (row["id"],),
        )
        conn.commit()
        return row["id"]

    cursor = conn.execute(
        "INSERT INTO projects (domain) VALUES (?)", (domain,)
    )
    conn.commit()
    return cursor.lastrowid


def save_analysis(conn: sqlite3.Connection, analysis_data: Dict) -> int:
    """Save analysis record. Returns analysis_id."""
    extra_data = analysis_data.pop("extra_data", None)
    if extra_data and isinstance(extra_data, dict):
        extra_data = json.dumps(extra_data)

    cursor = conn.execute(
        """INSERT INTO analyses (
            project_id, url, keyword, health_score,
            entity_coverage_score, heading_score, word_count_score,
            readability_score, link_score, client_word_count,
            competitor_avg_word_count, recommended_word_count_min,
            recommended_word_count_max, analysis_duration_seconds,
            competitors_analyzed, competitors_failed, extra_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            analysis_data["project_id"],
            analysis_data["url"],
            analysis_data["keyword"],
            analysis_data.get("health_score"),
            analysis_data.get("entity_coverage_score"),
            analysis_data.get("heading_score"),
            analysis_data.get("word_count_score"),
            analysis_data.get("readability_score"),
            analysis_data.get("link_score"),
            analysis_data.get("client_word_count"),
            analysis_data.get("competitor_avg_word_count"),
            analysis_data.get("recommended_word_count_min"),
            analysis_data.get("recommended_word_count_max"),
            analysis_data.get("analysis_duration_seconds"),
            analysis_data.get("competitors_analyzed"),
            analysis_data.get("competitors_failed"),
            extra_data,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def save_competitors(conn: sqlite3.Connection, analysis_id: int, competitors: List[Dict]):
    """Save competitor records for an analysis."""
    for comp in competitors:
        conn.execute(
            """INSERT INTO competitors (
                analysis_id, url, position, word_count,
                heading_count, entity_count, scrape_success, scrape_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                analysis_id,
                comp["url"],
                comp.get("position"),
                comp.get("word_count"),
                comp.get("heading_count"),
                comp.get("entity_count"),
                comp.get("scrape_success"),
                comp.get("scrape_method"),
            ),
        )
    conn.commit()


def save_entities(conn: sqlite3.Connection, analysis_id: int, entities: List[Dict]):
    """Save entity records for an analysis."""
    for ent in entities:
        conn.execute(
            """INSERT INTO entities (
                analysis_id, entity_text, entity_type,
                client_count, client_salience,
                competitor_frequency, competitor_avg_salience, gap_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                analysis_id,
                ent["entity_text"],
                ent.get("entity_type"),
                ent.get("client_count", 0),
                ent.get("client_salience", 0.0),
                ent.get("competitor_frequency", 0),
                ent.get("competitor_avg_salience", 0.0),
                ent.get("gap_status"),
            ),
        )
    conn.commit()


def get_analysis(conn: sqlite3.Connection, analysis_id: int) -> Optional[Dict]:
    """Get analysis by ID with all related data."""
    cursor = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,))
    row = cursor.fetchone()
    if not row:
        return None

    analysis = dict(row)

    # Parse extra_data JSON
    if analysis.get("extra_data"):
        try:
            analysis["extra_data"] = json.loads(analysis["extra_data"])
        except (json.JSONDecodeError, TypeError):
            analysis["extra_data"] = {}

    # Get competitors
    cursor = conn.execute(
        "SELECT * FROM competitors WHERE analysis_id = ?", (analysis_id,)
    )
    analysis["competitors"] = [dict(r) for r in cursor.fetchall()]

    # Get entities
    cursor = conn.execute(
        "SELECT * FROM entities WHERE analysis_id = ? ORDER BY competitor_frequency DESC",
        (analysis_id,),
    )
    analysis["entities"] = [dict(r) for r in cursor.fetchall()]

    return analysis


def get_previous_analysis(conn: sqlite3.Connection, url: str, keyword: str, exclude_id: int) -> Optional[Dict]:
    """Get the most recent previous analysis for the same URL + keyword."""
    cursor = conn.execute(
        """SELECT * FROM analyses
           WHERE url = ? AND keyword = ? AND id != ?
           ORDER BY created_at DESC LIMIT 1""",
        (url, keyword, exclude_id),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def get_analysis_history(conn: sqlite3.Connection, limit: int = 50) -> List[Dict]:
    """Get recent analyses with project info."""
    cursor = conn.execute(
        """SELECT a.*, p.domain
           FROM analyses a
           JOIN projects p ON a.project_id = p.id
           ORDER BY a.created_at DESC
           LIMIT ?""",
        (limit,),
    )
    return [dict(r) for r in cursor.fetchall()]


def save_gsc_data(conn: sqlite3.Connection, records: List[Dict], source_type: str = "queries"):
    """Save GSC CSV data. Clears existing data for this source_type first."""
    conn.execute("DELETE FROM gsc_data WHERE source_type = ?", (source_type,))
    for rec in records:
        conn.execute(
            """INSERT INTO gsc_data (source_type, url, keyword, clicks, impressions, ctr, position, opportunity_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                source_type,
                rec.get("url", ""),
                rec.get("keyword", ""),
                rec.get("clicks", 0),
                rec.get("impressions", 0),
                rec.get("ctr", 0.0),
                rec.get("position", 0.0),
                rec.get("opportunity_score", 0.0),
            ),
        )
    conn.commit()


def get_gsc_data(conn: sqlite3.Connection, source_type: str = None, limit: int = 100) -> List[Dict]:
    """Get GSC data sorted by opportunity score, optionally filtered by source_type."""
    if source_type:
        cursor = conn.execute(
            "SELECT * FROM gsc_data WHERE source_type = ? ORDER BY opportunity_score DESC LIMIT ?",
            (source_type, limit),
        )
    else:
        cursor = conn.execute(
            "SELECT * FROM gsc_data ORDER BY opportunity_score DESC LIMIT ?",
            (limit,),
        )
    return [dict(r) for r in cursor.fetchall()]


def save_api_usage(conn: sqlite3.Connection, analysis_id: Optional[int], endpoint: str, cost: float):
    """Log an API call and its cost."""
    conn.execute(
        "INSERT INTO api_usage (analysis_id, endpoint, cost) VALUES (?, ?, ?)",
        (analysis_id, endpoint, cost),
    )
    conn.commit()


def get_api_usage_total(conn: sqlite3.Connection, days: int = 30) -> Dict:
    """Get API usage summary for the last N days."""
    cursor = conn.execute(
        """SELECT COUNT(*) as call_count, COALESCE(SUM(cost), 0) as total_cost
           FROM api_usage
           WHERE timestamp >= datetime('now', ?)""",
        (f"-{days} days",),
    )
    row = cursor.fetchone()
    return {"call_count": row["call_count"], "total_cost": row["total_cost"]}


def clear_expired_cache(conn: sqlite3.Connection):
    """Remove expired cache entries."""
    conn.execute("DELETE FROM api_cache WHERE expires_at < datetime('now')")
    conn.execute("DELETE FROM scrape_cache WHERE expires_at < datetime('now')")
    conn.commit()


def clear_all_cache(conn: sqlite3.Connection):
    """Clear all cache entries."""
    conn.execute("DELETE FROM api_cache")
    conn.execute("DELETE FROM scrape_cache")
    conn.commit()
