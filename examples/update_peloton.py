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
    def __init__(self, sheet, cellrange, rows, columns,
                 column_for_key, column_for_value):
        self.columns = columns
        self.rows = rows
        self.range = cellrange
        self.column_name_to_column = {}
        self.next_empty_row = None

        self.value_cell_for_key = {}
        self.column_for_key = column_for_key
        self.column_for_value = column_for_value
        super(WorkoutSheet, self).__init__(sheet)

    def load(self):
        self.cell_list = self.sheet.range(self.range)

        for column in range(self.columns):
            self.column_name_to_column[self.cell_at(0, column).value] = column

        for row in range(1, self.rows):
            # empty?
            if self.cell_at(row, self.column_for_key).value == '':
                self.next_empty_row = row
                break

            key = pd.Timestamp(self.cell_at(row, self.column_for_key).value,
                               tz='America/Los_Angeles')
            self.value_cell_for_key[key] \
                = self.cell_at(row, self.column_for_value)

    def cell_at(self, row, col):
        return self.cell_list[self.columns * row + col]

    def exists(self, key):
        return key in self.value_cell_for_key

    def value(self, key):
        return self.value_cell_for_key[key].value

    def update(self, key, value):
        self.value_cell_for_key[key].value = value

    def append(self, row_dict):
        print("would add to row {}".format(self.next_empty_row))
        row = self.next_empty_row
        for key in row_dict.keys():
            col = self.column_name_to_column[key]
            self.cell_at(row, col).value = row_dict[key]
        self.next_empty_row += 1

    def sync(self):
        self.sheet.update_cells(self.cell_list)


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
        chrome_options.add_argument("--window-size=1920x1080")
        # Replaces browser User Agent from "HeadlessChrome".
        user_agent = "Chrome"
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


def update_peloton2(secrets, sheet):
    pw = WorkoutSheet(sheet,
                      secrets['sheet']['range'],
                      secrets['sheet']['rows'],
                      secrets['sheet']['columns'],
                      0, 1)
    pw.load()
    files = glob.glob("./tmp/*.csv")
    with open(files[0], "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_val = row['Workout Timestamp (PST)']
            ts = pd.Timestamp(ts_val, tz="America/Los_Angeles")
            print(ts, row['Total Output'])
            if not pw.exists(ts):
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
    print(secrets)
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
