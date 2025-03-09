import os
import requests
import argparse
import json
import re
import telebot
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from dotenv import load_dotenv


class TechBBSParser:
    def __init__(self, cpus):
        load_dotenv()
        self.cpus = cpus
        self.forum_url = "https://bbs.io-tech.fi"
        self.sub_url = "/forums/prosessorit-emolevyt-ja-muistit.73/"
        self.valid_type = "Myydään"
        self.bot_token = os.getenv("BOT_TOKEN")
        self.chat_id = os.getenv("CHAT_ID")
        self.bot = telebot.TeleBot(token=self.bot_token)


    def check_for_new_threads(self):
        """
        Function checks for new valid threads, removes old ones and sends an
        alert via Telegram bot.
        """
        # find and extract the thread titles and URLs
        thread_data = self.find_valid_threads()

        # compare the current thread data with the previous state here
        new_threads = []
        with open("thread_data.json", "r") as data:
            old_data = json.load(data)
            for thread in thread_data:
                for old_thread in old_data:
                    if thread["url"] == old_thread["url"]:
                        break
                else:
                    new_threads.append(thread)

        # append new data to old data
        for item in new_threads:
            old_data.append(item)

        # remove old threads (14 days old)
        data = self.remove_old_threads(old_data, 14)

        # dump data to a json file
        with open("thread_data.json", "w") as outfile:
            json.dump(data, outfile, indent=4)

        # if new threads are detected, send an alert
        if new_threads:
            self.print_logs("Found new items")
            self.print_logs(new_threads)
            self.send_alert(new_threads)

    def find_valid_threads(self):
        """Function finds valid threads for script to use.

        Function uses BeautifulSoup to scrape the website and parses needed
        data from the threads found in the website.

        Returns:
            list: List of valid threads
        """
        response = requests.get(self.forum_url + self.sub_url)
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

            thread_title = self.clean_string(thread_title) # clean thread title
            # check if thread type matches class variable and if thread title contains
            # wanted string defined in script arguments 
            if thread_type not in self.valid_type:
                continue
            if not any(cpu.lower() in thread_title.lower() for cpu in self.cpus):
                continue

            thread_url = f"{self.forum_url}{thread_items[1].get('href')}" # url to the thread

            date_cell = thread.find(
                "div", class_="structItem-cell structItem-cell--latest"
            )
            date_cell = date_cell.find("a").find("time")
            date = date_cell.get("datetime")

            # append thread to thread_data
            thread_data.append({"title": thread_title, "url": thread_url, "date": date})

        return thread_data

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
        today = datetime.now(timezone.utc)

        for i, thread in enumerate(threads):
            # convert thread date to datetime object
            date = datetime.fromisoformat(thread["date"])
            date_delta = today - date # thread age
            if date_delta.days > max_thread_age:
                threads.pop(i) # remove thread from list

        return threads

    def send_alert(self, threads):
        """Function sends Telegram bot alert from threads

        Threads defined in `threads` parameter will be parsed and sent via
        Telegram bot

        Args:
            threads (list): Threads to send alert of
        """
        alert_threads = self.parse_alert_threads(threads) # parse threads

        for item in alert_threads:
            message = f"*Uusi prossu myynnissä:*\n\n\U0001f579 *Tuote:* {item['model']}\n\U0001f4b5 *Hinta:* {item['price']}\n\U0001f4c6 *Ostettu:* {item['product_bought']}\n\U0001f9fe *Kuitti, takuu:* {item['warranty']}\n\U0001f4ce *Linkki:* [Tässä]({item['url']})\n"
            self.bot.send_message(
                self.chat_id,
                message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

    def parse_alert_threads(self, threads):
        """Function parses the list of threads and returns them as alert items.

        Alert items contain CPU model, price, bought date, warranty and thread url.

        Args:
            threads (list): Threads to parse.

        Returns:
            list: Alert items list
        """
        alert_items = []

        for thread in threads:
            response = requests.get(thread["url"])
            soup = BeautifulSoup(response.text, "html.parser")
            main_cell = soup.find("div", class_="bbWrapper")
            item_cells = main_cell.find_all("b")
            alert_item = {}
            for i, item in enumerate(item_cells[0:4]):
                item = item.next_sibling[2:]
                if i == 0:
                    alert_item["model"] = item
                elif i == 1:
                    alert_item["price"] = item
                elif i == 2:
                    alert_item["product_bought"] = item
                elif i == 3:
                    alert_item["warranty"] = item
            alert_item["url"] = thread["url"]
            alert_items.append(alert_item)

        return alert_items

    def clean_string(self, string):
        """Function cleans the string from newline and tab characters

        Args:
            string (str): String to clean.

        Returns:
            str: Cleaned string.
        """
        #  remove \n and \t
        st = string.replace("\t", "").replace("\n", "")
        return st

    def print_logs(self, log):
        """Function prints logs with a timestamp.
        """
        time_stamp = datetime.now(timezone.utc)
        print(f"{time_stamp}: {log}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parser for finding new GPU listings")
    parser.add_argument(
        "--cpus",
        nargs="+",
        type=str,
        help="List of CPU entries to seek",
        required=True,
    )
    args = parser.parse_args()

    bbs = TechBBSParser(args.cpus)
    bbs.check_for_new_threads()
