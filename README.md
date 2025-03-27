# TechBBS-Telegram-alert
 Python script for scraping TechBBS marketplace and sending alerts for wanted CPUs via Telegram bot.

# Setting up environment
Python virtual environment is recommended for using this script. To create Python virtual environment, run the following command inside the repository folder:

```
python3 -m venv .venv
```

To install packages required by the script, run:

On Linux/MacOS:

```
.venv/bin/python3 -m pip install -r requirements.txt
```

On Windows:

```
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For script to work, you'll need `.env` file for storing your Telegram bot API token and chat ID.

Create a file called `.env` inside the repository folder containing following parameters:

`CPUS` contains the wanted CPUs to search for seperated by comma.

`GPUS` contains the wanted GPUs to search for seperated by comma.

`BOT_TOKEN` has the token of your Telegram bot.

`CHAT_ID` has the chat ID of your bot's chat.

`DEFAULT_TIMEOUT` is default timeout in seconds for requests.

`MAX_THREAD_AGE` is maximum thread age before old threads are deleted from data JSON.

```
CPUS="5900X,9800X3D"
GPUS="7900XTX,3070 Ti"
BOT_TOKEN="your_bot_token"
CHAT_ID="your_chat_id"
DEFAULT_TIMEOUT="60"
MAX_THREAD_AGE="14"
```

For more info about creating a Telegram bot and getting the token and chat ID, look [here](https://gist.github.com/nafiesl/4ad622f344cd1dc3bb1ecbe468ff9f8a).

# Running the script

On Linux/MacOS:

```
.venv/bin/python3 techbbs_parser.py
```

On Windows:

```
.venv\Scripts\python.exe techbbs_parser.py
```