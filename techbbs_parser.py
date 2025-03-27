import os
import asyncio
import argparse
import json
import re
import logging
import requests
import aiohttp
import telebot
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from dotenv import load_dotenv


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")  # Telegram bot token from environment variables
CHAT_ID = os.getenv("CHAT_ID", "")  # Telegram chat ID from environment variables
DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", 60))  # Default timeout for requests
MAX_THREAD_AGE = int(os.getenv("MAX_THREAD_AGE", 14))  # Maximum thread age in days
CPUS = [
    cpu.strip() for cpu in os.getenv("CPUS", "").split(",") if cpu.strip()
]  # Clean and split CPUs
GPUS = [
    gpu.strip() for gpu in os.getenv("GPUS", "").split(",") if gpu.strip()
]  # Clean and split GPUs
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(message)s"
)  # Logging configuration


class TechBBSParser:
    """
    Class for scraping TechBBS forum marketplace and finding desired CPUs
    and sending alerts via Telegram bot.

    Attributes:
        cpus (list): List of CPUs to search for.
        forum_url (str): Base URL of the TechBBS forum.
        sub_url (str): Sub-URL of the specific forum section.
        valid_type (str): Type of threads to look for.
        bot (telebot.TeleBot): Instance of the Telegram bot.
    """

    def __init__(self):
        self.forum_url = "https://bbs.io-tech.fi"
        self.valid_type = "Myydään"
        if not BOT_TOKEN or not CHAT_ID:
            raise ValueError("Missing BOT_TOKEN or CHAT_ID in environment variables.")
        self.bot = telebot.TeleBot(token=BOT_TOKEN)

    def check_for_new_threads(self):
        """
        Checks for new valid threads, removes old ones and sends an
        alert via Telegram bot.

        This method compares the current threads with previously stored threads,
        identifies new threads, and sends an alert if new threads are found. It
        also updates the stored threads by removing old ones.

        Raises:
            ValueError: If environment variables BOT_TOKEN or CHAT_ID are missing.
        """
        # get thread data for CPUs and GPUs
        if CPUS:
            sub_url = "/forums/prosessorit-emolevyt-ja-muistit.73/"
            cpu_data = self.find_valid_threads(CPUS, sub_url)
        if GPUS:
            sub_url = "/forums/naytonohjaimet.74/"
            gpu_data = self.find_valid_threads(GPUS, sub_url)

        # combine CPU and GPU data
        thread_data = cpu_data + gpu_data if CPUS and GPUS else cpu_data or gpu_data

        new_threads = []
        old_data = self.load_old_data()

        # compare thread urls with old data and create a list with new threads
        existing_urls = {thread["url"] for thread in old_data}
        new_threads = [
            thread for thread in thread_data if thread["url"] not in existing_urls
        ]

        # if new threads are detected, send an alert
        if new_threads:
            self.print_logs(f"Found new items:\n{new_threads}")
            self.send_alert(new_threads)

            old_data.extend(new_threads)  # append new threads
            old_data = self.remove_old_threads(old_data)  # Remove old ones

            with open("thread_data.json", "w", encoding="utf-8") as outfile:
                json.dump(old_data, outfile, indent=4)

    def find_valid_threads(self, items, sub_url):
        """Finds valid threads for script to use.

        This method uses BeautifulSoup to scrape the website and parses needed
        data from the threads found on the website. It filters threads based on
        the specified type and CPUs of interest.

        Returns:
            list: List of valid threads containing title, URL, and date.
        """
        try:
            response = requests.get(self.forum_url + sub_url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.print_logs(f"Network error occurred: {e}")
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        thread_data = []

        self.print_logs(f"Checking for valid threads for items: {items}")

        # find and extract the thread titles and URLs
        thread_elements = soup.find_all(
            "div",
            class_=re.compile(
                "structItem structItem--thread is-prefix1 js-inlineModContainer js-threadListItem-*"
            ),
        )

        # loop trough threads
        for thread in thread_elements:
            main_cell = thread.find(
                "div", class_="structItem-cell structItem-cell--main"
            )

            # extract thread type and title
            thread_items = main_cell.find_all("a")
            thread_type, thread_title = (
                thread_items[0].find("span").text,
                thread_items[1].text,
            )

            thread_title = self.clean_string(thread_title)  # clean thread title

            # check if thread title contains wanted string defined in environment variables
            if thread_type not in self.valid_type:
                continue
            if not any(item.lower() in thread_title.lower() for item in items):
                continue

            thread_url = (
                f"{self.forum_url}{thread_items[1].get('href')}"  # url to the thread
            )

            date_cell = thread.find(
                "div", class_="structItem-cell structItem-cell--latest"
            )
            date_cell = date_cell.find("a").find("time")
            date = date_cell.get("datetime", "Unknown")

            # check the product type
            if "prosessorit" in sub_url:
                product_type = "prossu"
            if "naytonohjaimet" in sub_url:
                product_type = "näyttis"

            # append thread to thread_data
            thread_data.append(
                {
                    "product": product_type,
                    "title": thread_title,
                    "url": thread_url,
                    "date": date,
                }
            )

        return thread_data

    def load_old_data(self, file_path="thread_data.json"):
        """Loads old thread data from a JSON file, handling file absence gracefully.

        Args:
            file_path (str): path to JSON file containing the old data

        Returns:
            list: loaded JSON object, or empty list
        """
        if not os.path.exists(file_path):
            return []  # return an empty list if file doesn't exist

        try:
            with open(file_path, "r", encoding="utf-8") as data:
                return json.load(data)
        except (IOError, json.JSONDecodeError) as e:
            self.print_logs(f"Error loading old data: {e}")
            return []

    def remove_old_threads(self, threads: list, max_thread_age: int = MAX_THREAD_AGE):
        """Function removes old threads from the thread list

        Threads older than `max_thread_age` parameter definition will be removed
        from `threads` list parameter.

        Args:
            threads (list): list of threads
            max_thread_age (int): maximum thread age

        Returns:
            list: List of threads after removing old threads
        """
        cleaned_list = []
        today = datetime.now(timezone.utc)

        for thread in threads:
            if (today - datetime.fromisoformat(thread["date"])).days <= max_thread_age:
                cleaned_list.append(thread)

        return cleaned_list

    def send_alert(self, threads):
        """Function sends Telegram bot alert from threads

        Threads defined in `threads` parameter will be parsed and sent via
        Telegram bot

        Args:
            threads (list): Threads to send alert of
        """
        alert_items = self.parse_alert_threads(threads)  # parse threads

        for item in alert_items:
            message = (
                f"*Uusi {item['product']} myynnissä:*\n\n"
                f"\U0001f579 *Tuote:* {item['model']}\n"
                f"\U0001f4b5 *Hinta:* {item['price']}\n"
                f"\U0001f4c6 *Ostettu:* {item['product_bought']}\n"
                f"\U0001f9fe *Kuitti, takuu:* {item['warranty']}\n"
                f"\U0001f4ce *Linkki:* [Tässä]({item['url']})\n"
            )

            try:
                self.bot.send_message(
                    CHAT_ID,
                    message,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
            except telebot.apihelper.ApiException as e:
                self.print_logs(f"Failed to send alert: {e}")

    def parse_alert_threads(self, threads):
        """Wrapper function to call the async function synchronously

        Args:
            threads (list): Threads to parse

        Returns:
            list: Alert items list
        """
        return asyncio.run(self.parse_alert_threads_async(threads))

    async def fetch_page(self, session, url):
        """Fetch the page content asynchronously

        Args:
            session (obj): aiohttp client session
            url (str): url for the request

        Returns:
            str: response text
        """
        try:
            async with session.get(url, timeout=60) as response:
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            self.print_logs(f"Failed to fetch {url}: {e}")
            return ""

    async def parse_alert_threads_async(self, threads):
        """Asynchronous version of parse_alert_threads

        Args:
            threads (list): Threads to parse

        Returns:
            list: Alert items list
        """
        alert_items = []

        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_page(session, thread["url"]) for thread in threads]
            pages = await asyncio.gather(*tasks)  # fetch all pages concurrently

            for i, page_content in enumerate(pages):
                soup = BeautifulSoup(page_content, "html.parser")
                main_cell = soup.find("div", class_="bbWrapper")

                if not main_cell:
                    continue  # skip if page structure is different

                item_cells = main_cell.find_all("b")
                alert_item = {}

                for j, item in enumerate(item_cells[:4]):  # extract up to 4 items
                    item = item.next_sibling[2:] if item.next_sibling else "Unknown"
                    if j == 0:
                        alert_item["model"] = item
                    elif j == 1:
                        alert_item["price"] = item
                    elif j == 2:
                        alert_item["product_bought"] = item
                    elif j == 3:
                        alert_item["warranty"] = item

                # add product_type from thread_data
                alert_item["product"] = threads[i]["product"]

                alert_item["url"] = threads[i]["url"]
                alert_items.append(alert_item)

        return alert_items

    def clean_string(self, string):
        """Function cleans the string from newline and tab characters

        Args:
            string (str): String to clean.

        Returns:
            str: Cleaned string.
        """
        return string.replace("\t", "").replace("\n", "").strip()

    def print_logs(self, log):
        """Function prints logs with a timestamp."""
        logging.info(log)


if __name__ == "__main__":
    bbs = TechBBSParser()
    bbs.check_for_new_threads()
