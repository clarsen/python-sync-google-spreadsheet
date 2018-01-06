import os
import time
from datetime import datetime

import click
import gspread
import pandas as pd
import yaml
from beddit.client import BedditClient
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

import sync_google_spreadsheet.sheet_adapter


class SleepSheet(sync_google_spreadsheet.sheet_adapter.SheetAdapter):
    def __init__(self, sheet, cellrange, rows, columns,
                 column_for_key, column_for_value):
        self.columns = columns
        self.rows = rows
        self.range = cellrange
        self.value_cell_for_key = {}
        self.column_for_key = column_for_key
        self.column_for_value = column_for_value
        super(SleepSheet, self).__init__(sheet)

    def load(self):
        self.cell_list = self.sheet.range(self.range)
        for row in range(1, self.rows):
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

    def sync(self):
        self.sheet.update_cells(self.cell_list)


class BedditSheet(SleepSheet):
    def __init__(self, sheet, cellrange, rows, columns):
        super(BedditSheet, self).__init__(sheet, cellrange,
                                          rows, columns, 1, 5)


class ResmedSheet(SleepSheet):
    def __init__(self, sheet, cellrange, rows, columns):
        super(ResmedSheet, self).__init__(sheet, cellrange,
                                          rows, columns, 0, 6)


def update_resmed(secrets, sheet):
    rs = ResmedSheet(sheet, secrets['sheet']['range'],
                     secrets['sheet']['rows'],
                     secrets['sheet']['columns'])
    rs.load()

    username = secrets['resmed']['user']
    password = secrets['resmed']['password']
    page_delay = 25

    chromedriver_location = './assets/chromedriver'
    chrome_options = Options()
    chrome_options.add_argument('--dns-prefetch-disable')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--lang=en-US')
    chrome_options.add_argument('--disable-setuid-sandbox')

    # Headless chrome doesn't seem to work with this site.
    # chrome_options.add_argument('--headless')
    # chrome_options.add_argument("--window-size=1920x1080")
    # # Replaces browser User Agent from "HeadlessChrome".
    # user_agent = "Chrome"
    # chrome_options.add_argument('--user-agent={user_agent}'
    #                             .format(user_agent=user_agent))
    chrome_prefs = {
        'intl.accept_languages': 'en-US'
    }
    chrome_options.add_experimental_option('prefs', chrome_prefs)

    browser = webdriver.Chrome(chromedriver_location,
                               chrome_options=chrome_options)
    browser.implicitly_wait(page_delay)

    # login
    browser.get('https://myair.resmed.com/Default.aspx')
    time.sleep(5)
    lang_elem = browser.find_element_by_xpath(
                  "//span[text()='United States']")
    if lang_elem is not None:
        ActionChains(browser).move_to_element(lang_elem).click().perform()
    print("choose language")

    # apparently not having the password field visible makes it hard to
    # navigate to it

    input_email = browser.find_elements_by_xpath(
        "//input[@name='ctl00$ctl00$PageContent$MainPageContent$textBoxEmailAddress']")
    browser.execute_script("return arguments[0].scrollIntoView();",
                           input_email[0])
    browser.execute_script("window.scrollBy(0, -150);")
    ActionChains(browser).move_to_element(input_email[0]).\
        click().send_keys(username).perform()
    print("input email")

    input_password = browser.find_elements_by_xpath(
        "//input[@name='ctl00$ctl00$PageContent$MainPageContent$textBoxPassword']")
    browser.execute_script("return arguments[0].scrollIntoView();",
                           input_password[0])
    browser.execute_script("window.scrollBy(0, -150);")
    ActionChains(browser).move_to_element(input_password[0]). \
        click().send_keys(password).perform()
    print("input password")

    login_button = browser.find_element_by_xpath("//span[text()='Sign in']")
    browser.execute_script("return arguments[0].scrollIntoView();",
                           login_button)
    browser.execute_script("window.scrollBy(0, -150);")
    ActionChains(browser).move_to_element(login_button).click().perform()
    print("login")

    # Get sleep usage
    usage_button = browser.find_element_by_xpath(
        "//label[text()='Usage hours']")
    ActionChains(browser).move_to_element(usage_button).click().perform()

    usage_scores = browser.execute_script("return myScores;")

    curmonth = datetime.now().month
    curyear = datetime.now().year
    for day in usage_scores:
        # data from site doesn't have year.
        if day['MonthName'] == 'December' and curmonth == 1:
            year = curyear - 1
        else:
            year = curyear
        ts = pd.Timestamp("{} {}".format(day['Date'], year),
                          tz="America/Los_Angeles")
        resmed_dur = day['UsageDisplay']
        print("{} -> {}".format(ts, resmed_dur))
        if rs.exists(ts):
            if rs.value(ts) != resmed_dur:
                print("would update", ts)
                rs.update(ts, resmed_dur)
            else:
                print("already matches")
    rs.sync()


def update_beddit(secrets, sheet):
    bs = BedditSheet(sheet, secrets['sheet']['range'],
                     secrets['sheet']['rows'],
                     secrets['sheet']['columns'])
    bs.load()
    client = BedditClient(secrets['beddit']['user'],
                          secrets['beddit']['password'])
    start_date = datetime.strptime(secrets['beddit']['start_date'], "%m/%d/%Y")
    end_date = datetime.strptime(secrets['beddit']['end_date'], "%m/%d/%Y")

    sleeps = client.get_sleeps(start=start_date, end=end_date)
    for sleep in sleeps:
        # print(sleep.date.strftime('%Y-%m-%d'), sleep.property.total_sleep_score)
        beddit_dur = "{}:{:02d}".format(
          sleep.property.primary_sleep_period_total_sleep_duration / 3600,
          (sleep.property.primary_sleep_period_total_sleep_duration % 3600)/60)

        print(sleep.date.strftime('%Y-%m-%d'), beddit_dur)
        ts = pd.Timestamp(sleep.date.strftime('%Y-%m-%d'),
                          tz='America/Los_Angeles')
        if bs.exists(ts):
            if bs.value(ts) != beddit_dur:
                print("would update", ts)
                bs.update(ts, beddit_dur)
            else:
                print("already matches")
    bs.sync()


@click.group()
def main():
    pass


@main.command()
def test():
    init_common()


def init_common():
    with open(os.path.expanduser("~/.secrets.yaml"), "r") as f:
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
def beddit():
    secrets, sheet = init_common()
    update_beddit(secrets, sheet)


@main.command()
def resmed():
    secrets, sheet = init_common()
    update_resmed(secrets, sheet)


if __name__ == "__main__":
    main()
