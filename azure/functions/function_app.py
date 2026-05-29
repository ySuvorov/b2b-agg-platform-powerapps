"""
fetch-supplier-feed — Azure Functions v4 (Python 3.11, decorator model)

HTTP GET  /api/feed/{supplier_id}
Returns the raw JSON feed blob for the requested supplier.

Supplier routing:
    rosshinaopt / 1  →  feed-supplier-en  / feed.json
    tyrecenter-spb / 2  →  feed-supplier-ru  / feed.json
    koleso-ru / 3  →  feed-supplier-xml / feed.json

Local fallback: when AZURE_STORAGE_CONNECTION_STRING is absent or equals
"UseDevelopmentStorage=true", blobs are served from the local filesystem at
LOCAL_FEEDS_PATH (default: ../../data/feeds, relative to the function-app root).
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Final

import azure.functions as func

import sku_matcher

# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supplier → storage mapping
# ---------------------------------------------------------------------------

# Maps any recognised supplier_id to (container_name, blob_name)
SUPPLIER_MAP: Final[dict[str, tuple[str, str]]] = {
    "rosshinaopt": ("feed-supplier-en", "feed.json"),
    "1":           ("feed-supplier-en", "feed.json"),
    "tyrecenter-spb": ("feed-supplier-ru", "feed.json"),
    "2":           ("feed-supplier-ru", "feed.json"),
    "koleso-ru":   ("feed-supplier-xml", "feed.json"),
    "3":           ("feed-supplier-xml", "feed.json"),
}

_DEV_STORAGE_MARKER: Final[str] = "UseDevelopmentStorage=true"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_local_mode(conn_str: str | None) -> bool:
    """Return True when Azure Storage should NOT be used (local dev mode)."""
    return not conn_str or conn_str.strip() == _DEV_STORAGE_MARKER


def _read_blob_azure(conn_str: str, container: str, blob_name: str) -> bytes:
    """Download *blob_name* from *container* using the SDK."""
    # Import lazily so the module still loads in local mode without the SDK.
    from azure.storage.blob import BlobServiceClient  # type: ignore[import]

    service_client = BlobServiceClient.from_connection_string(conn_str)
    blob_client = service_client.get_blob_client(container=container, blob=blob_name)
    stream = blob_client.download_blob()
    return stream.readall()


def _read_blob_local(container: str, blob_name: str) -> bytes:
    """Read a feed file from the local filesystem (developer fallback)."""
    feeds_path_env = os.environ.get("LOCAL_FEEDS_PATH", "")
    if feeds_path_env:
        base = pathlib.Path(feeds_path_env)
    else:
        # Resolve relative to the function-app root (two levels up from this file)
        base = pathlib.Path(__file__).parent.parent.parent / "data" / "feeds"

    file_path = base / container / blob_name
    logger.info("Local mode: reading feed from %s", file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Local feed file not found: {file_path}")

    return file_path.read_bytes()


def _build_error_response(status_code: int, message: str) -> func.HttpResponse:
    body = json.dumps({"error": message, "status": status_code})
    return func.HttpResponse(
        body=body,
        status_code=status_code,
        mimetype="application/json",
    )


# ---------------------------------------------------------------------------
# HTTP trigger
# ---------------------------------------------------------------------------


@app.route(route="feed/{supplier_id}", methods=["GET", "POST"])
def fetch_supplier_feed(req: func.HttpRequest) -> func.HttpResponse:
    """Return a supplier's aggregated feed blob as JSON."""

    supplier_id: str = req.route_params.get("supplier_id", "").strip().lower()

    logger.info(
        "fetch_supplier_feed called | supplier_id=%s | method=%s",
        supplier_id,
        req.method,
    )

    # ------------------------------------------------------------------
    # Route supplier_id to storage coordinates
    # ------------------------------------------------------------------
    if supplier_id not in SUPPLIER_MAP:
        logger.warning("Unknown supplier_id: %s", supplier_id)
        return _build_error_response(
            404,
            f"Supplier '{supplier_id}' not found. "
            f"Known IDs: {sorted(set(SUPPLIER_MAP.keys()))}",
        )

    container, blob_name = SUPPLIER_MAP[supplier_id]
    logger.info("Mapped to container=%s blob=%s", container, blob_name)

    # ------------------------------------------------------------------
    # Fetch blob
    # ------------------------------------------------------------------
    conn_str: str | None = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")

    try:
        if _is_local_mode(conn_str):
            logger.info("Running in local/dev mode — using filesystem fallback")
            raw: bytes = _read_blob_local(container, blob_name)
        else:
            raw = _read_blob_azure(conn_str, container, blob_name)  # type: ignore[arg-type]
    except FileNotFoundError as exc:
        logger.warning("Feed file not found: %s", exc)
        return _build_error_response(404, str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to read blob container=%s blob=%s: %s", container, blob_name, exc
        )
        return _build_error_response(
            500,
            f"Internal error while fetching feed for supplier '{supplier_id}'. "
            "Check Application Insights for details.",
        )

    # ------------------------------------------------------------------
    # Validate that the blob is valid JSON before returning
    # ------------------------------------------------------------------
    try:
        # Parse and re-serialise to normalise encoding (UTF-8, compact).
        payload = json.loads(raw)
        body = json.dumps(payload, ensure_ascii=False)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error(
            "Feed blob is not valid JSON | container=%s blob=%s | error=%s",
            container,
            blob_name,
            exc,
        )
        return _build_error_response(
            502,
            f"Feed for supplier '{supplier_id}' is malformed (not valid JSON).",
        )

    logger.info(
        "Returning feed | supplier_id=%s | bytes=%d", supplier_id, len(body)
    )

    return func.HttpResponse(
        body=body,
        status_code=200,
        mimetype="application/json",
        headers={
            "X-Supplier-Id": supplier_id,
            "X-Container": container,
        },
    )


# ---------------------------------------------------------------------------
# normalize-sku — deterministic + fuzzy SKU resolver (Stages 1–2)
# ---------------------------------------------------------------------------


@app.route(route="normalize-sku", methods=["POST"])
def normalize_sku(req: func.HttpRequest) -> func.HttpResponse:
    """Resolve a raw supplier name to a canonical product.

    Request body (JSON):
        {
          "raw_name": "MICHELIN Latitude Sport 3 245/45R20 103W XL Run on Flat *",
          "raw_sku":  "ML S3-24545R20-RFT-BMW",          # optional, echoed back
          "catalog":  [ { "id", "name", "brand", "model",
                          "width", "profile", "diameter",
                          "load_index", "speed_index",
                          "homologation", "runflat", "extraload" }, ... ]
        }

    `catalog` is normally supplied by the calling flow (a Dataverse "List rows"
    of b2b_canonicalproduct). If omitted, a bundled snapshot (catalog.json next
    to this file) is used so the endpoint is self-contained for testing.

    Response (JSON): the MatchResult — decision/method/confidence, the parsed
    attributes, and the ranked candidates. The flow uses `decision` to branch:
    ExactKey/Fuzzy → auto-bind; Ambiguous → AI tie-break / admin; NewCandidate
    → admin (new product).
    """
    try:
        payload = req.get_json()
    except ValueError:
        return _build_error_response(400, "Request body must be valid JSON.")

    raw_name = (payload or {}).get("raw_name", "").strip()
    if not raw_name:
        return _build_error_response(400, "Field 'raw_name' is required.")

    catalog = (payload or {}).get("catalog")
    if not catalog:
        try:
            snapshot = pathlib.Path(__file__).parent / "catalog.json"
            catalog = json.loads(snapshot.read_text(encoding="utf-8")) if snapshot.exists() else []
        except Exception:  # noqa: BLE001
            catalog = []

    if not catalog:
        return _build_error_response(
            422,
            "No canonical catalog available: pass 'catalog' in the body or "
            "deploy a catalog.json snapshot next to the function.",
        )

    try:
        result = sku_matcher.match(raw_name, catalog)
    except Exception as exc:  # noqa: BLE001
        logger.exception("normalize-sku failed for raw_name=%s: %s", raw_name, exc)
        return _build_error_response(500, "Matcher error — see Application Insights.")

    body_obj = {
        "raw_name": raw_name,
        "raw_sku": (payload or {}).get("raw_sku", ""),
        "decision": result.decision,
        "method": result.method,
        "confidence": result.confidence,
        "canonical_id": result.canonical_id,
        "canonical_name": result.canonical_name,
        "parsed": result.parsed,
        "candidates": result.candidates,
    }
    logger.info(
        "normalize-sku | decision=%s conf=%.3f | %s → %s",
        result.decision, result.confidence, raw_name, result.canonical_name,
    )
    return func.HttpResponse(
        body=json.dumps(body_obj, ensure_ascii=False),
        status_code=200,
        mimetype="application/json",
    )
