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


class SleepSheet_resmed(sync_google_spreadsheet.sheet_adapter.SheetAdapter):
    def __init__(self, sheet):

        def rowkey(row):
            datestr = row['Going to sleep at']
            ts = pd.Timestamp(datestr,
                              tz='America/Los_Angeles')

            return ts

        super(SleepSheet_resmed, self).__init__(sheet, 1,
                                                rowkey,
                                                non_empty_column='Going to sleep at',
                                                )


class SleepSheet_beddit(sync_google_spreadsheet.sheet_adapter.SheetAdapter):
    def __init__(self, sheet):

        def rowkey(row):
            datestr = row['Waking up']
            ts = pd.Timestamp(datestr,
                              tz='America/Los_Angeles')

            return ts

        super(SleepSheet_beddit, self).__init__(sheet, 1,
                                                rowkey,
                                                non_empty_column='Waking up'
                                                )


def update_resmed(secrets, sheet):
    username = secrets['resmed']['user']
    password = secrets['resmed']['password']
    page_delay = 25

    chromedriver_location = './assets/chromedriver'
    chrome_options = Options()
    chrome_options.add_argument('--dns-prefetch-disable')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--lang=en-US')
    chrome_options.add_argument('--disable-setuid-sandbox')

    # Headless chrome does work when user agent set properly
    chrome_options.add_argument('--headless')
    chrome_options.add_argument("--window-size=1200x1080")
    # Replaces browser User Agent from "HeadlessChrome".
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36"
    chrome_options.add_argument('--user-agent={user_agent}'
                                .format(user_agent=user_agent))
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

    def sleep_streamer():
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
            yield {
                'Going to sleep at': ts,
                'myAir duration': resmed_dur,
                }

    rs = SleepSheet_resmed(sheet)
    rs.load()

    for row in sleep_streamer():
        if rs.has(row):
            idx = rs.row_for_kvhash(row)
            if rs.row(idx)['myAir duration'] != row['myAir duration']:
                rs.update_row(idx, row, ['myAir duration'])
            else:
                print("already matches")
        else:
            print("not found")

    rs.sync()


def update_beddit(secrets, sheet):
    client = BedditClient(secrets['beddit']['user'],
                          secrets['beddit']['password'])
    start_date = datetime.strptime(secrets['beddit']['start_date'], "%m/%d/%Y")
    end_date = datetime.strptime(secrets['beddit']['end_date'], "%m/%d/%Y")
    sleeps = client.get_sleeps(start=start_date, end=end_date)

    def sleep_streamer():
        for sleep in sleeps:
            ts = pd.Timestamp(sleep.date.strftime('%Y-%m-%d'),
                              tz='America/Los_Angeles')
            beddit_dur = "{}:{:02d}".format(
                sleep.property.primary_sleep_period_total_sleep_duration / 3600,
                (sleep.property.primary_sleep_period_total_sleep_duration % 3600)/60)
            row = {
                'Waking up': ts,
                'beddit duration': beddit_dur
            }
            print(row)
            yield row

    bs = SleepSheet_beddit(sheet)
    bs.load()

    for row in sleep_streamer():
        if bs.has(row):
            idx = bs.row_for_kvhash(row)
            if bs.row(idx)['beddit duration'] != row['beddit duration']:
                bs.update_row(idx, row, ['beddit duration'])
            else:
                print("already matches")
        else:
            print("not found")
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
