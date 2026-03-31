# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUntypedFunctionDecorator=false, reportUnusedFunction=false, reportAttributeAccessIssue=false

from flask import Flask, jsonify

from config import get_settings, load_env  # pyright: ignore[reportImplicitRelativeImport]
from api.envelope import error, success  # pyright: ignore[reportImplicitRelativeImport]
from infra.db import check_db_connectivity  # pyright: ignore[reportImplicitRelativeImport]
from api.instruments import instruments_bp  # pyright: ignore[reportImplicitRelativeImport]
from api.ingestion import ingestion_bp  # pyright: ignore[reportImplicitRelativeImport]
from api.bars import bars_bp  # pyright: ignore[reportImplicitRelativeImport]
from api.indicators import indicators_bp  # pyright: ignore[reportImplicitRelativeImport]
from api.analysis import analysis_bp  # pyright: ignore[reportImplicitRelativeImport]
from api.research import research_bp  # pyright: ignore[reportImplicitRelativeImport]
from api.market import market_bp  # pyright: ignore[reportImplicitRelativeImport]
from api.stocks import stocks_bp  # pyright: ignore[reportImplicitRelativeImport]
from api.telegram import telegram_bp  # pyright: ignore[reportImplicitRelativeImport]
from api.candidate_pool import candidate_pool_bp  # pyright: ignore[reportImplicitRelativeImport]


def create_app() -> Flask:
    load_env()
    app = Flask(__name__)
    settings = get_settings()
    
    # Register blueprints
    app.register_blueprint(instruments_bp)
    app.register_blueprint(ingestion_bp)
    app.register_blueprint(bars_bp)
    app.register_blueprint(indicators_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(stocks_bp)
    app.register_blueprint(telegram_bp)
    app.register_blueprint(candidate_pool_bp)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/")
    def index():
        return jsonify(
            {
                "service": "quantdog-api",
                "message": "QuantDog API scaffold is running",
                "research_enabled": settings.research_enabled,
                "enable_ai_analysis": settings.enable_ai_analysis,
            }
        )

    @app.get("/api/v1/health")
    def v1_health():
        # Must not require DB connectivity.
        return success({"status": "ok"})

    @app.get("/api/v1/readyz")
    def v1_readyz():
        result = check_db_connectivity(settings.database_url, timeout_seconds=1.0)
        if result.ok:
            return success({"status": "ok"})
        return error(
            "not ready",
            error_type=result.error_type or "db_unavailable",
            detail=result.detail or "DB connectivity check failed",
            status_code=503,
        )

    @app.get("/api/v1/openapi.json")
    def v1_openapi():
        # Keep this minimal and static; no external OpenAPI deps.
        doc = {
            "openapi": "3.0.3",
            "info": {
                "title": "QuantDog API",
                "version": "0.1.0",
                "description": "QuantDog API-first stock analysis MVP.",
            },
            "paths": {
                "/api/v1/health": {
                    "get": {
                        "summary": "Liveness probe",
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/EnvelopeSuccessHealth"}
                                    }
                                },
                            }
                        },
                    }
                },
                "/api/v1/readyz": {
                    "get": {
                        "summary": "Readiness probe (DB connectivity)",
                        "responses": {
                            "200": {
                                "description": "Ready",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/EnvelopeSuccessReady"}
                                    }
                                },
                            },
                            "503": {
                                "description": "Not ready",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/EnvelopeError"}
                                    }
                                },
                            },
                        },
                    }
                },
                "/api/v1/openapi.json": {
                    "get": {
                        "summary": "OpenAPI document",
                        "responses": {
                            "200": {
                                "description": "OpenAPI 3.x JSON",
                                "content": {"application/json": {"schema": {"type": "object"}}},
                            }
                        },
                    }
                },
                "/api/v1/candidate-pools/latest": {
                    "get": {
                        "summary": "Latest daily candidate pool snapshot",
                        "responses": {
                            "200": {
                                "description": "Latest candidate pool snapshot",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/CandidatePoolLatestResponse"}
                                    }
                                },
                            },
                            "404": {
                                "description": "No candidate snapshot found",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/EnvelopeError"}
                                    }
                                },
                            },
                        },
                    }
                },
                "/api/v1/telegram/messages": {
                    "post": {
                        "summary": "Queue telegram message delivery",
                        "parameters": [
                            {
                                "in": "header",
                                "name": "Authorization",
                                "required": False,
                                "schema": {"type": "string"},
                                "description": "Bearer token using the Telegram API token.",
                            },
                            {
                                "in": "header",
                                "name": "X-Telegram-Api-Token",
                                "required": False,
                                "schema": {"type": "string"},
                                "description": "Alternative header for the Telegram API token.",
                            },
                            {
                                "in": "header",
                                "name": "Idempotency-Key",
                                "required": False,
                                "schema": {"type": "string"},
                                "description": "Optional idempotency token used to derive the dedupe key.",
                            }
                        ],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["chat_id", "text"],
                                        "properties": {
                                            "chat_id": {"type": "integer"},
                                            "text": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        },
                        "responses": {
                            "202": {
                                "description": "Telegram message enqueued",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/TelegramMessageEnqueueResponse"}
                                    }
                                },
                            },
                            "400": {
                                "description": "Invalid request",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/EnvelopeError"}
                                    }
                                },
                            },
                            "401": {
                                "description": "Unauthorized",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/EnvelopeError"}
                                    }
                                },
                            },
                        },
                    }
                },
            },
            "components": {
                "schemas": {
                    "EnvelopeError": {
                        "type": "object",
                        "required": ["code", "msg", "error"],
                        "properties": {
                            "code": {"type": "integer", "enum": [0]},
                            "msg": {"type": "string"},
                            "error": {
                                "type": "object",
                                "required": ["type", "detail"],
                                "properties": {
                                    "type": {"type": "string"},
                                    "detail": {"type": "string"},
                                },
                            },
                        },
                    },
                    "EnvelopeSuccessHealth": {
                        "type": "object",
                        "required": ["code", "msg", "data"],
                        "properties": {
                            "code": {"type": "integer", "enum": [1]},
                            "msg": {"type": "string", "enum": ["success"]},
                            "data": {
                                "type": "object",
                                "required": ["status"],
                                "properties": {"status": {"type": "string", "enum": ["ok"]}},
                            },
                        },
                    },
                    "EnvelopeSuccessReady": {
                        "type": "object",
                        "required": ["code", "msg", "data"],
                        "properties": {
                            "code": {"type": "integer", "enum": [1]},
                            "msg": {"type": "string", "enum": ["success"]},
                            "data": {
                                "type": "object",
                                "required": ["status"],
                                "properties": {"status": {"type": "string", "enum": ["ok"]}},
                            },
                        },
                    },
                    "CandidatePoolLatestResponse": {
                        "type": "object",
                        "required": ["code", "msg", "data"],
                        "properties": {
                            "code": {"type": "integer", "enum": [1]},
                            "msg": {"type": "string", "enum": ["success"]},
                            "data": {
                                "type": "object",
                                "required": ["candidates"],
                                "properties": {
                                    "candidates": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/CandidatePoolMember"},
                                    },
                                },
                            },
                        },
                    },
                    "CandidatePoolMember": {
                        "type": "object",
                        "required": ["symbol", "rank", "rvol", "pct_change", "dollar_volume", "last_price"],
                        "properties": {
                            "symbol": {"type": "string"},
                            "rank": {"type": "integer"},
                            "rvol": {"type": "number"},
                            "pct_change": {"type": "number"},
                            "dollar_volume": {"type": "number"},
                            "last_price": {"type": "number"},
                        },
                    },
                    "TelegramMessageEnqueueResponse": {
                        "type": "object",
                        "required": ["code", "msg", "data"],
                        "properties": {
                            "code": {"type": "integer", "enum": [1]},
                            "msg": {"type": "string"},
                            "data": {
                                "type": "object",
                                "required": ["job_id", "chat_id", "dedupe_key"],
                                "properties": {
                                    "job_id": {"type": ["string", "null"]},
                                    "chat_id": {"type": "integer"},
                                    "dedupe_key": {"type": ["string", "null"]},
                                },
                            },
                        },
                    },
                }
            },
        }
        return jsonify(doc)

    return app
