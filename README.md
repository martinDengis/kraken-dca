# kraken-dca

A simple Dollar-Cost Averaging (DCA) helper for executing periodic market buy orders on Kraken. Mainly aimed for Kraken Pro (offers lower fees) as DCA option is available on the base app already - so make sure to create API keys for the Kraken Pro app version.

## Features

- YAML configuration for API keys, strategies, logging and Discord notifications.
- Executes multiple DCA strategies (pair + EUR amount) in one run.
- Logs to file and console.
- Optional Discord webhook notifications for success/failure of each order.
- GitHub Actions workflow to run automatically on the 1st of every month (UTC) or manually.

## Setup

1. Install dependencies:

    ```bash
    pip install requests pyyaml
    ```

2. Copy the example config and edit values:

    ```bash
    cp config.example.yaml config.yaml
    ```

    Edit `config.yaml` and fill in:

    - `api.key` / `api.secret`: Your Kraken API credentials (must allow Query Funds & Create & Modify Orders). Keep them secret.
    - `dca.strategies`: List of pairs with the amount in EUR you wish to spend each run.
    - `logging.discord_webhook`: (Optional) Discord webhook URL for notifications.

3. Run locally:

    ```bash
    python main.py
    ```

## Configuration Example

```yaml
api:
  key: YOUR_KRAKEN_API_KEY
  secret: YOUR_KRAKEN_API_SECRET

dca:
  dry_run: true   # If true, no real orders are placed (simulation only)
  strategies:
    - pair: ETH/EUR
      amount_eur: 25.0
    - pair: BTC/EUR
      amount_eur: 25.0

logging:
  level: INFO
  file: kraken_dca.log
  discord_webhook: https://discord.com/api/webhooks/XXXX/YYY
```

### Dry Run Mode

- Set `dca.dry_run: true` to simulate the run (volumes and prices computed, no orders sent).
- Set `dca.dry_run: false` (or omit the key) to execute real market buy orders.
- Balance check still runs in dry run mode for validation.

## Discord Webhook

Create a webhook in your Discord channel (Server Settings -> Integrations -> Webhooks) and paste the URL into the config (or GitHub secret `DISCORD_WEBHOOK`).

## GitHub Actions (Automated Monthly Run)

A workflow file at `.github/workflows/monthly-dca.yml` is included. It triggers:

- On the 1st day of each month at 00:00 UTC.
- Manually via the Actions tab (`workflow_dispatch`).

### Required Repository Secrets

Set these in your repository settings -> Secrets and variables -> Actions:

- `KRAKEN_API_KEY`
- `KRAKEN_API_SECRET`
- `DCA_PAIR_1` / `DCA_AMOUNT_1`
- `DCA_PAIR_2` / `DCA_AMOUNT_2` (Adjust workflow or extend as needed.)
- `DISCORD_WEBHOOK` (optional)

To add more than two strategies in GitHub Actions, modify the workflow section that builds `config.yaml`.

## Notes

- The script converts EUR amounts to asset volume using the current ask price before placing a market order.
- Rounding is to 8 decimals; adjust if needed.
- Always test with small amounts first.

## Disclaimer

This code is provided *as is*, without warranty of any kind. Use at your own risk. Market orders may incur slippage. You are solely responsible for securing your API keys and for any trades executed with this code. I assume no liability for any losses, damages, or other consequences resulting from its use.
