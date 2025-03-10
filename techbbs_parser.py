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


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


class TechBBSParser:
    """
    Class for scraping TechBBS forum marketplace and finding desired CPUs
    and sending alerts via Telegram bot.
    """

    def __init__(self, cpus):
        load_dotenv()
        self.cpus = cpus
        self.forum_url = "https://bbs.io-tech.fi"
        self.sub_url = "/forums/prosessorit-emolevyt-ja-muistit.73/"
        self.valid_type = "Myydään"
        self.bot_token = os.getenv("BOT_TOKEN")
        self.chat_id = os.getenv("CHAT_ID")
        if not self.bot_token or not self.chat_id:
            raise ValueError("Missing BOT_TOKEN or CHAT_ID in environment variables.")
        self.bot = telebot.TeleBot(token=self.bot_token)

    def check_for_new_threads(self):
        """
        Function checks for new valid threads, removes old ones and sends an
        alert via Telegram bot.
        """
        # find and extract the thread titles and URLs
        thread_data = self.find_valid_threads()

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
            old_data = self.remove_old_threads(old_data, 14)  # Remove old ones

            with open("thread_data.json", "w", encoding="utf-8") as outfile:
                json.dump(old_data, outfile, indent=4)

    def find_valid_threads(self):
        """Function finds valid threads for script to use.

        Function uses BeautifulSoup to scrape the website and parses needed
        data from the threads found in the website.

        Returns:
            list: List of valid threads
        """
        response = requests.get(self.forum_url + self.sub_url, timeout=60)
        soup = BeautifulSoup(response.text, "html.parser")
        thread_data = []

        self.print_logs("Checking for valid threads")

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
            # check if thread type matches class variable and if thread title contains
            # wanted string defined in script arguments
            if thread_type not in self.valid_type:
                continue
            if not any(cpu.lower() in thread_title.lower() for cpu in self.cpus):
                continue

            thread_url = (
                f"{self.forum_url}{thread_items[1].get('href')}"  # url to the thread
            )

            date_cell = thread.find(
                "div", class_="structItem-cell structItem-cell--latest"
            )
            date_cell = date_cell.find("a").find("time")
            date = date_cell.get("datetime", "Unknown")

            # append thread to thread_data
            thread_data.append({"title": thread_title, "url": thread_url, "date": date})

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

        with open(file_path, "r", encoding="utf-8") as data:
            try:
                return json.load(data)
            except json.JSONDecodeError:
                return []  # return an empty list if JSON is malformed

    def remove_old_threads(self, threads: list, max_thread_age: int = 14):
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
            message = f"*Uusi prossu myynnissä:*\n\n" \
                      f"\U0001f579 *Tuote:* {item['model']}\n" \
                      f"\U0001f4b5 *Hinta:* {item['price']}\n" \
                      f"\U0001f4c6 *Ostettu:* {item['product_bought']}\n" \
                      f"\U0001f9fe *Kuitti, takuu:* {item['warranty']}\n" \
                      f"\U0001f4ce *Linkki:* [Tässä]({item['url']})\n"
            self.bot.send_message(
                self.chat_id,
                message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

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
        async with session.get(url, timeout=60) as response:
            return await response.text()

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
    parser = argparse.ArgumentParser(description="Parser for finding new GPU listings")
    parser.add_argument(
        "--cpus",
        nargs="+",
        type=str,
        help="List of CPU entries to seek, seperated by whitespace",
        required=True,
    )
    args = parser.parse_args()

    bbs = TechBBSParser(args.cpus)
    bbs.check_for_new_threads()
