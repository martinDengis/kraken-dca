import time
import logging
from typing import List, Dict, Any, Optional
import requests

LOGGER = logging.getLogger("kraken_dca")

def send_discord_message(webhook_url: str, content: str = "", embed: dict = None):
    if not webhook_url:
        LOGGER.debug("No Discord webhook configured; skipping message")
        return
    payload: Dict[str, Any] = {}
    if content:
        payload["content"] = content
    if embed:
        payload["embeds"] = [embed]
    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        if resp.status_code >= 300:
            LOGGER.warning("Failed to send Discord message (status=%s): %s", resp.status_code, resp.text[:300])
    except Exception as e:
        LOGGER.exception("Exception while sending Discord message: %s", e)

def _timestamp():
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

def create_start_embed(strategy_count: int) -> dict:
    return {
        "title": "🚀 Kraken DCA Bot Started",
        "description": f"Starting DCA execution with **{strategy_count}** strategies",
        "color": 0x3498db,
        "timestamp": _timestamp(),
        "footer": {"text": "Kraken DCA Bot"}
    }

def create_dry_run_embed(pair: str, amount_eur: float, price: float, volume: float) -> dict:
    return {
        "title": "🧪 Dry Run Executed",
        "color": 0xf39c12,
        "fields": [
            {"name": "Trading Pair", "value": f"`{pair}`", "inline": True},
            {"name": "Amount (EUR)", "value": f"€{amount_eur:.2f}", "inline": True},
            {"name": "Current Price", "value": f"€{price:.4f}", "inline": True},
            {"name": "Volume", "value": f"{volume:.8f}", "inline": True}
        ],
        "timestamp": _timestamp(),
        "footer": {"text": "Kraken DCA Bot • Dry Run Mode"}
    }

def create_success_embed(pair: str, volume: float, price: float, txid: List[str]) -> dict:
    return {
        "title": "✅ Order Successfully Placed",
        "color": 0x27ae60,
        "fields": [
            {"name": "Trading Pair", "value": f"`{pair}`", "inline": True},
            {"name": "Volume", "value": f"{volume:.8f}", "inline": True},
            {"name": "Price", "value": f"€{price:.4f}", "inline": True},
            {"name": "Transaction ID", "value": f"`{', '.join(txid) if txid else 'N/A'}`", "inline": False}
        ],
        "timestamp": _timestamp(),
        "footer": {"text": "Kraken DCA Bot • Live Trading"}
    }

def create_error_embed(pair: str, volume: float, price: float, error: List[str]) -> dict:
    return {
        "title": "❌ Order Failed",
        "color": 0xe74c3c,
        "fields": [
            {"name": "Trading Pair", "value": f"`{pair}`", "inline": True},
            {"name": "Volume", "value": f"{volume:.8f}", "inline": True},
            {"name": "Price", "value": f"€{price:.4f}", "inline": True},
            {"name": "Error", "value": f"```{', '.join(error)}```", "inline": False}
        ],
        "timestamp": _timestamp(),
        "footer": {"text": "Kraken DCA Bot • Error"}
    }

def create_exception_embed(pair: str, error: str) -> dict:
    return {
        "title": "⚠️ Exception Occurred",
        "color": 0xff6b35,
        "fields": [
            {"name": "Trading Pair", "value": f"`{pair}`", "inline": True},
            {"name": "Exception", "value": f"```{str(error)[:1000]}```", "inline": False}
        ],
        "timestamp": _timestamp(),
        "footer": {"text": "Kraken DCA Bot • Exception"}
    }

def create_completion_embed() -> dict:
    return {
        "title": "🏁 DCA Run Completed",
        "description": "All strategies have been processed successfully",
        "color": 0x9b59b6,
        "timestamp": _timestamp(),
        "footer": {"text": "Kraken DCA Bot"}
    }

def create_insufficient_funds_embed(required: float, available: float) -> dict:
    return {
        "title": "🛑 Insufficient EUR Balance",
        "color": 0xc0392b,
        "fields": [
            {"name": "Required (EUR)", "value": f"€{required:.2f}", "inline": True},
            {"name": "Available (EUR)", "value": f"€{available:.2f}", "inline": True},
            {"name": "Status", "value": "Cancelling all planned trades.", "inline": False}
        ],
        "timestamp": _timestamp(),
        "footer": {"text": "Kraken DCA Bot • Pre-Trade Check"}
    }
