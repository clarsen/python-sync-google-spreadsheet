import os
import time
import glob
import csv

import click
import gspread
import pandas as pd
import yaml

from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

import sync_google_spreadsheet.sheet_adapter


class WorkoutSheet(sync_google_spreadsheet.sheet_adapter.SheetAdapter):
    def __init__(self, sheet_adapter):

        def rowkey(row):
            key = pd.Timestamp(row['Workout Timestamp (PST)'],
                               tz='America/Los_Angeles')
            return key

        super(WorkoutSheet, self).__init__(sheet_adapter, 1,
                                           rowkey,
                                           non_empty_column='Workout Timestamp (PST)')


def update_peloton(secrets):
    username = secrets['peloton']['user']
    password = secrets['peloton']['password']
    page_delay = 25

    chromedriver_location = './assets/chromedriver'
    chrome_options = Options()
    chrome_options.add_argument('--dns-prefetch-disable')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--lang=en-US')
    chrome_options.add_argument('--disable-setuid-sandbox')

    # with headless chrome, doesn't seem to be able to trigger the download
    if False:
        chrome_options.add_argument('--headless')
        chrome_options.add_argument("--window-size=1200x1080")
        # Replaces browser User Agent from "HeadlessChrome".
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36"

        chrome_options.add_argument('--user-agent="{user_agent}"'
                                    .format(user_agent=user_agent))
    chrome_prefs = {
        'intl.accept_languages': 'en-US',
        'download.default_directory': './tmp',
    }
    chrome_options.add_experimental_option('prefs', chrome_prefs)

    browser = webdriver.Chrome(chromedriver_location,
                               chrome_options=chrome_options)
    browser.implicitly_wait(page_delay)

    # login
    browser.get('https://www.onepeloton.com/profile')
    time.sleep(5)

    input_email = browser.find_elements_by_xpath(
        "//input[@name='usernameOrEmail']")
    browser.execute_script("return arguments[0].scrollIntoView();",
                           input_email[0])
    browser.execute_script("window.scrollBy(0, -150);")
    ActionChains(browser).move_to_element(input_email[0]).\
        click().send_keys(username).perform()
    print("input email")

    input_password = browser.find_elements_by_xpath(
        "//input[@name='password']")
    browser.execute_script("return arguments[0].scrollIntoView();",
                           input_password[0])
    browser.execute_script("window.scrollBy(0, -150);")
    ActionChains(browser).move_to_element(input_password[0]). \
        click().send_keys(password).perform()
    print("input password")

    login_button = browser.find_element_by_xpath("//input[@value='Sign in']")
    browser.execute_script("return arguments[0].scrollIntoView();",
                           login_button)
    browser.execute_script("window.scrollBy(0, -150);")
    ActionChains(browser).move_to_element(login_button).click().perform()
    print("login")

    button = browser.find_element_by_xpath(
                  "//button[text()='Download Workout History']")
    ActionChains(browser).move_to_element(button).click().perform()


def csv_streamer(fn):
    with open(fn, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def update_peloton2(secrets, sheet):
    pw = WorkoutSheet(sheet)
    pw.load()

    files = glob.glob("./tmp/*.csv")
    for row in csv_streamer(files[0]):
        print(row['Workout Timestamp (PST)'], row['Total Output'])
        if not pw.has(row):
            pw.append(row)
    pw.sync()


@click.group()
def main():
    pass


@main.command()
def test():
    init_common()


def init_common():
    with open(os.path.expanduser("~/.secrets-peloton.yaml"), "r") as f:
        secrets = yaml.load(f)
    SCOPE = ["https://spreadsheets.google.com/feeds"]
    SECRETS_FILE = os.path.expanduser(secrets['sheet']['secrets_file'])
    SPREADSHEET = secrets['sheet']['name']
    credentials = ServiceAccountCredentials \
        .from_json_keyfile_name(SECRETS_FILE, SCOPE)
    # Authenticate using the signed key
    gss_client = gspread.authorize(credentials)
    gss = gss_client.open(SPREADSHEET)
    sheet = gss.worksheet(secrets['sheet']['worksheet_name'])

    return secrets, sheet


@main.command()
def peloton():
    secrets, sheet = init_common()
    # first get data
    update_peloton(secrets)
    # then update sheet
    update_peloton2(secrets, sheet)


@main.command()
def peloton2():
    secrets, sheet = init_common()
    update_peloton2(secrets, sheet)


if __name__ == "__main__":
    main()
