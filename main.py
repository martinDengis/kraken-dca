import requests
import hashlib
import hmac
import base64
import json
import time
import os
import logging
from dataclasses import dataclass
from typing import List
from discord_utils import (
    send_discord_message,
    create_start_embed,
    create_dry_run_embed,
    create_success_embed,
    create_error_embed,
    create_exception_embed,
    create_completion_embed,
    create_insufficient_funds_embed,
)

try:
    import yaml  # type: ignore
except ImportError:  # Fallback if not installed yet
    yaml = None  # type: ignore

DEFAULT_BASE_URL = os.getenv("KRAKEN_API_BASE", "https://api.kraken.com")
LOGGER = logging.getLogger("kraken_dca")

@dataclass
class Strategy:
    pair: str
    amount_eur: float


def load_config(path: str = "config.yaml"):
    if not os.path.exists(path):
        raise FileNotFoundError("Configuration file 'config.yaml' not found. Create it from 'config.example.yaml'.")
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)  # type: ignore
    return data


def setup_logging(cfg):
    log_cfg = cfg.get('logging', {})
    level = getattr(logging, log_cfg.get('level', 'INFO'))
    log_file = log_cfg.get('file', 'kraken_dca.log')

    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    LOGGER.info("Logging initialized (level=%s, file=%s)", log_cfg.get('level', 'INFO'), log_file)


def check_kraken_status(base_url: str = DEFAULT_BASE_URL):
    response = requests.get(f'{base_url}/0/public/SystemStatus', timeout=15)
    status = response.json().get("result", {}).get("status", "Unknown")
    LOGGER.info("Kraken System Status: %s", status)
    if status != "online":
        raise Exception("API is not online. Aborting.")


def get_nonce() -> str:
   return str(int(time.time() * 1000))


def get_ask_price(pair: str, base_url: str = DEFAULT_BASE_URL):
    resp = requests.get(f'{base_url}/0/public/Ticker?pair={pair}', timeout=15).json()
    ask_price = resp['result'][pair]['a'][0]
    return float(ask_price)


def sign(private_key: str, message: bytes) -> str:
   return base64.b64encode(
      hmac.new(
         key=base64.b64decode(private_key),
         msg=message,
         digestmod=hashlib.sha512,
      ).digest()
   ).decode()


def get_signature(private_key: str, data: str, nonce: str, path: str) -> str:
   return sign(
      private_key=private_key,
      message=path.encode() + hashlib.sha256(
            (nonce + data)
         .encode()
      ).digest()
   )


def pass_market_order(api_key, api_secret, pair, volume, base_url: str = DEFAULT_BASE_URL):
    url_path = '/0/private/AddOrder'
    url = f'{base_url}{url_path}'

    nonce = get_nonce()
    post_data = {
        'nonce': nonce,
        'ordertype': 'market',
        'type': 'buy',
        'volume': volume,
        'pair': pair
    }
    post_data_encoded = '&'.join([f"{key}={value}" for key, value in post_data.items()])

    headers = {
        'API-Key': api_key,
        'API-Sign': get_signature(api_secret, post_data_encoded, nonce, url_path)
    }

    response = requests.post(url, headers=headers, data=post_data, timeout=30)
    return response.json()


def eur_to_volume(pair: str, amount_eur: float, base_url: str = DEFAULT_BASE_URL) -> float:
    price = get_ask_price(pair, base_url=base_url)
    volume = amount_eur / price
    return round(volume, 8)


def get_balance(api_key: str, api_secret: str, base_url: str = DEFAULT_BASE_URL):
    url_path = '/0/private/Balance'
    url = f'{base_url}{url_path}'
    nonce = get_nonce()
    post_data = {'nonce': nonce}
    post_data_encoded = '&'.join([f"{k}={v}" for k, v in post_data.items()])
    headers = {
        'API-Key': api_key,
        'API-Sign': get_signature(api_secret, post_data_encoded, nonce, url_path)
    }
    resp = requests.post(url, headers=headers, data=post_data, timeout=30)
    return resp.json()


def ensure_sufficient_funds(api_key: str, api_secret: str, strategies: List[Strategy], discord_webhook: str, base_url: str = DEFAULT_BASE_URL):
    total_required = sum(s.amount_eur for s in strategies)
    bal_resp = get_balance(api_key, api_secret, base_url=base_url)
    if bal_resp.get('error'):
        LOGGER.error("Error fetching balance: %s", bal_resp['error'])
        embed = create_exception_embed("ALL", f"Balance fetch failed: {bal_resp['error']}")
        send_discord_message(discord_webhook, embed=embed)
        raise SystemExit("Aborting due to balance fetch error.")
    balances = bal_resp.get('result', {})
    available_eur = float(balances.get('ZEUR', balances.get('EUR', 0.0)))
    LOGGER.info("Pre-trade balance check: required=%.2f available=%.2f", total_required, available_eur)
    if available_eur + 1e-8 < total_required:  # tiny epsilon
        LOGGER.warning("Insufficient funds: required=%.2f available=%.2f. Aborting.", total_required, available_eur)
        embed = create_insufficient_funds_embed(total_required, available_eur)
        send_discord_message(discord_webhook, embed=embed)
        raise SystemExit("Insufficient EUR balance. Trades cancelled.")


def execute_strategies(api_key: str, api_secret: str, strategies: List[Strategy], discord_webhook: str, base_url: str = DEFAULT_BASE_URL, dry_run: bool = False):
    results = []
    for strat in strategies:
        try:
            LOGGER.info("Processing strategy pair=%s amount_eur=%.2f", strat.pair, strat.amount_eur)
            price = get_ask_price(strat.pair, base_url=base_url)
            volume = eur_to_volume(strat.pair, strat.amount_eur, base_url=base_url)
            LOGGER.info("Calculated volume %.8f at price %.2f for pair %s", volume, price, strat.pair)

            if dry_run:
                status_msg = f"DRY-RUN | {strat.pair} | eur={strat.amount_eur} | est_price={price:.2f} | volume={volume}"
                LOGGER.info(status_msg)
                embed = create_dry_run_embed(strat.pair, strat.amount_eur, price, volume)
                send_discord_message(discord_webhook, embed=embed)
                results.append({
                    "dry_run": True,
                    "pair": strat.pair,
                    "amount_eur": strat.amount_eur,
                    "est_price": price,
                    "volume": volume
                })
                continue

            order_resp = pass_market_order(api_key, api_secret, strat.pair, volume, base_url=base_url)
            if order_resp.get('error'):
                status_msg = f"FAILED | {strat.pair} | volume={volume} | price={price} | error={order_resp['error']}"
                LOGGER.error(status_msg)
                embed = create_error_embed(strat.pair, volume, price, order_resp['error'])
                send_discord_message(discord_webhook, embed=embed)
            else:
                txid = order_resp.get('result', {}).get('txid', [])
                status_msg = f"SUCCESS | {strat.pair} | volume={volume} | price={price} | txid={txid}"
                LOGGER.info(status_msg)
                embed = create_success_embed(strat.pair, volume, price, txid)
                send_discord_message(discord_webhook, embed=embed)
            results.append(order_resp)
        except Exception as e:
            LOGGER.exception("Exception handling strategy for pair %s", strat.pair)
            embed = create_exception_embed(strat.pair, str(e))
            send_discord_message(discord_webhook, embed=embed)
    return results


if __name__ == "__main__":
    if yaml is None:
        raise SystemExit("pyyaml not installed. Please install with 'pip install pyyaml'.")

    cfg = load_config()
    setup_logging(cfg)

    api_key = cfg['api']['key']
    api_secret = cfg['api']['secret']
    discord_webhook = cfg.get('logging', {}).get('discord_webhook', '')

    # Determine base URL (config overrides env; env overrides default)
    base_url = cfg.get('api', {}).get('base_url', os.getenv("KRAKEN_API_BASE", DEFAULT_BASE_URL))
    LOGGER.info("Using Kraken API base URL: %s", base_url)

    strategies_cfg = cfg.get('dca', {}).get('strategies', [])
    strategies = [Strategy(pair=s['pair'], amount_eur=float(s['amount_eur'])) for s in strategies_cfg]

    dry_run = bool(cfg.get('dca', {}).get('dry_run', False))
    LOGGER.info("Loaded %d strategies (dry_run=%s)", len(strategies), dry_run)

    # Perform security / balance check before any execution
    ensure_sufficient_funds(api_key, api_secret, strategies, discord_webhook, base_url=base_url)

    # Send start message (only if funds are sufficient)
    start_embed = create_start_embed(len(strategies))
    send_discord_message(discord_webhook, embed=start_embed)

    check_kraken_status(base_url=base_url)
    execute_strategies(api_key, api_secret, strategies, discord_webhook, base_url=base_url, dry_run=dry_run)

    # Send completion message
    completion_embed = create_completion_embed()
    send_discord_message(discord_webhook, embed=completion_embed)
    LOGGER.info("DCA run completed.")