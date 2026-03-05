# Initialize SQLite database with tables

from quantdog.config import load_env, get_settings
from quantdog.infra.sqlalchemy import get_engine
from sqlalchemy import text


def init_db():
    load_env()
    settings = get_settings()
    
    if settings.database_url is None:
        print("ERROR: DATABASE_URL not set")
        return 1
    
    engine = get_engine(settings.database_url)
    
    print(f"Initializing database: {settings.database_url}")
    
    with engine.connect() as conn:
        # Create instruments table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS instruments (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                exchange TEXT,
                type TEXT,
                currency TEXT,
                active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create bars_1d table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bars_1d (
                symbol TEXT NOT NULL,
                bar_date DATE NOT NULL,
                ts_utc BIGINT NOT NULL,
                open NUMERIC(18, 6) NOT NULL,
                high NUMERIC(18, 6) NOT NULL,
                low NUMERIC(18, 6) NOT NULL,
                close NUMERIC(18, 6) NOT NULL,
                volume BIGINT NOT NULL,
                adjusted BOOLEAN NOT NULL DEFAULT 0,
                source TEXT NOT NULL,
                PRIMARY KEY (symbol, bar_date, adjusted),
                FOREIGN KEY (symbol) REFERENCES instruments(symbol)
            )
        """))
        
        # Create jobs table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}',
                state TEXT NOT NULL,
                dedupe_key TEXT NOT NULL,
                locked_by TEXT,
                locked_at TIMESTAMP,
                heartbeat_at TIMESTAMP,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                last_error TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create research_runs table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS research_runs (
                run_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                requested_at TIMESTAMP NOT NULL,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                status TEXT NOT NULL,
                final_decision TEXT,
                final_confidence INTEGER,
                baseline_used BOOLEAN NOT NULL DEFAULT 0,
                quality_score INTEGER,
                error_summary TEXT,
                config_json TEXT NOT NULL DEFAULT '{}'
            )
        """))
        
        # Create research_agent_outputs table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS research_agent_outputs (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                phase INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                status TEXT NOT NULL,
                schema_version TEXT,
                output_json TEXT NOT NULL DEFAULT '{}',
                validation_errors_json TEXT NOT NULL DEFAULT '[]',
                duration_ms INTEGER,
                model_id TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(run_id, phase, agent_name),
                FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
            )
        """))
        
        conn.commit()
    
    print("Database initialized successfully!")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(init_db())
