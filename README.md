# steam-sale-monitor

Small script that sends a Telegram message when a Steam game goes on sale. No dependencies beyond Python 3.

## Setup

1. Copy the example config and put in your game:

   ```
   cp steam_games.example.json steam_games.json
   ```

   Each entry needs the Steam `appid` (the number in the store URL, `store.steampowered.com/app/<appid>/...`) and a display `name`. `min_discount` is optional and defaults to 1, meaning any discount triggers an alert. Set it to 30 to only hear about 30% or better.

2. Create a `.env` file next to the script, or export the variables:

   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_CHAT_ID=123456789
   ```

3. Try it without sending anything:

   ```
   python3 steam_sale_monitor.py --dry-run
   ```

4. Schedule it, for example every 3 hours:

   ```
   0 */3 * * * /usr/bin/python3 /path/to/steam_sale_monitor.py >> /path/to/steam_sale_monitor.log 2>&1
   ```

## Behaviour

- Prices are fetched from the Steam store API for the country in `STEAM_COUNTRY` (default `es`, so prices are in EUR).
- You get one alert per sale. A new alert is sent only if the sale price drops further, or after the game has gone back to full price and then is discounted again.
- Alert state is kept in `state/steam_sale_monitor.json`. Credentials, your game list and state are gitignored.
- The exit code is non-zero if a price lookup or Telegram call failed, which is handy for cron monitoring.
