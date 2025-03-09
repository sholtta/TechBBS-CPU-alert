# TechBBS-CPU-alert
 Python script for scraping TechBBS marketplace and sending alerts for wanted CPUs via Telegram bot.

# Setting up environment
Python virtual environment is recommended for using this script. To create Python virtual environment, run the following command inside the repository folder:

```
python3 -m venv .venv
```

To install packages required by the script, run:

```
.venv/bin/python3 -m pip install -r requirements.txt
```

For script to work, you'll need `.env` file for storing your Telegram bot API token and chat ID.

Create a file called `.env` inside the repository folder containing following parameters:

```
BOT_TOKEN="your_bot_token"
CHAT_ID="your_chat_id"
```

For more info about creating a Telegram bot and getting the token and chat ID, look [here](https://core.telegram.org/bots/features#botfather).

# Running the script

You can pass wanted CPUs after `--cpus` flag seperated by whitespace. For example:
```
.venv/bin/python3 iotech.py --cpus 7800X3D 9900K 9800X3D
```