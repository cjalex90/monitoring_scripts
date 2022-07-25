#!./.venv/bin/python3

import os
import sys
import time
import json
import random
import logging
import logging.handlers
from datetime import datetime, timedelta

from pyzabbix import ZabbixMetric, ZabbixSender
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service


ZABBIX_SERVER = "zabbix.domain.local"
ZABBIX_HOST = "nicru"
URL_PREFIX = "https://www.nic.ru/manager/payment.cgi?step=pay.forecast&date="
TRIES = 3  # number of attempts
LOG_MAXSIZE = 1048576
TERM = 60

ACCOUNTS = [
    12345,
    23456,
    34567
]
ACCOUNT_PASSWORD = ""

PATH_DIRECTORY = f"{os.path.dirname(os.path.abspath(__file__))}/"
BROWSER_TIMEOUT = random.randint(40, 60)
LOG_TIMEFORMAT = "%Y.%m.%d %H:%M:%S"


def log_setup():
    log_handler = logging.handlers.RotatingFileHandler(
        PATH_DIRECTORY + "debug.log",
        maxBytes=LOG_MAXSIZE,
        backupCount=5)
    formatter = logging.Formatter(
        "%(asctime)s %(message)s", LOG_TIMEFORMAT)
    log_handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(log_handler)


class Zabbix:
    def __init__(self, zabbix_server):
        self.zabbix_server = zabbix_server
        self.packet = []

    def add_metric(self, zabbix_host, key, value):
        self.packet.append(ZabbixMetric(zabbix_host, key, value))

    def send(self):
        ZabbixSender(ZABBIX_SERVER).send(self.packet)


def get_discovery_data(accounts):
    items = {"data": []}
    for account in accounts:
        account_dict = {"{#CONTRACT}": account}
        items["data"].append(account_dict)
    discovery_data = json.dumps(items)
    return discovery_data


def main():

    log_setup()
    zabbix = Zabbix(ZABBIX_SERVER)
    date_feature = datetime.now() + timedelta(days=TERM)
    url = URL_PREFIX + date_feature.strftime("%d.%m.%Y")

    for account in ACCOUNTS:
        attempt = 1
        while attempt <= TRIES:
            try:
                logging.info(f"account {account} attempt number: {attempt}")
                # Browser preparing
                s = Service(PATH_DIRECTORY + "geckodriver")
                options = webdriver.FirefoxOptions()
                options.headless = True  # Option to run browser without GUI
                driver = webdriver.Firefox(options=options, service=s)
                # Open url and authorization
                driver.get(url)
                time.sleep(BROWSER_TIMEOUT)
                logging.info(f"account {account} authorization")
                input_login = driver.find_element(By.ID, "login")
                input_login.clear()
                input_login.send_keys(account)
                input_password = driver.find_element(By.ID, "password")
                input_password.clear()
                input_password.send_keys(ACCOUNT_PASSWORD)
                driver.find_element(By.ID, "bind").click()
                time.sleep(BROWSER_TIMEOUT)

                # Searching for balance data
                balance = driver.find_elements(
                    By.TAG_NAME, "tr.light")[1].find_elements(
                        By.TAG_NAME, "td")[1].find_element(
                            By.TAG_NAME, "b").text
                balance = balance.split(".")[0]
                balance_after_date = driver.find_element(
                    By.CLASS_NAME, "good2").find_elements(
                        By.TAG_NAME, "strong")[1].text
                balance_after_date = balance_after_date.split(".")[0]
                zabbix.add_metric(
                    ZABBIX_HOST,
                    f"nicru.balance.[{account}]",
                    balance
                )
                zabbix.add_metric(
                    ZABBIX_HOST,
                    f"nicru.balance_after_{TERM}_days.[{account}]",
                    balance_after_date
                )
                driver.close()
                driver.quit()
                break
            except Exception as e:
                attempt += 1
                print(e, file=sys.stderr)
                logging.error(f"account {account} error:\n{e}")
                driver.close()
                driver.quit()
                pass

        else:
            zabbix.add_metric(ZABBIX_HOST, "nicru.balance.status", 0)
            zabbix.send()
            exit()

    zabbix.add_metric(
        ZABBIX_HOST,
        "nicru.discovery",
        get_discovery_data(ACCOUNTS)
    )
    zabbix.add_metric(ZABBIX_HOST, "nicru.balance.status", 1)
    zabbix.send()


if __name__ == "__main__":
    main()
