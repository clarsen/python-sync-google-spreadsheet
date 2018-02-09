import yaml
import click
import gspread
import os
import csv
import glob
import datetime
import re

from oauth2client.service_account import ServiceAccountCredentials

import sync_google_spreadsheet.sheet_adapter


def mdy_dt(string):
    return datetime.datetime.strptime(string, "%m/%d/%Y")


def dollar_str_to_val(x):
    match = re.match(r"\$?([\d\.,]+)", x)
    if match:
        val = match.group(1)
        val = val.replace(',', '')
    else:
        val = ''
    return val


class CategorizerSheet(object):
    """
    Transaction pattern matcher using spreadsheet as pattern input
    """
    def __init__(self, sheet):
        self.patmatch = []
        rows = sheet.row_count
        columns = sheet.col_count
        cell_list = sheet.range(1, 1, rows, columns)
        col_for_key = {}
        for column in range(columns):
            col_for_key[cell_list[column].value] = column
        transtype_col = col_for_key['Transaction type']
        cat_col = col_for_key['Category']
        freq_col = col_for_key['Frequency']
        desc_pat_col = col_for_key['Description pattern']
        desc_exact_col = col_for_key['Description exact']
        amount_col = col_for_key['Amount']
        for row in range(1, rows):
            if cell_list[row * columns + desc_pat_col].value == '' and \
               cell_list[row * columns + desc_exact_col].value == '' and \
               cell_list[row * columns + transtype_col].value == '':
                break
            transtype = cell_list[row * columns + transtype_col].value
            if transtype == '':
                transtype = None
            cat = cell_list[row * columns + cat_col].value
            freq = cell_list[row * columns + freq_col].value
            if freq == '':
                freq = None
            desc_pat = cell_list[row * columns + desc_pat_col].value
            desc_exact = cell_list[row * columns + desc_exact_col].value
            amount = cell_list[row * columns + amount_col].value
            if amount == '':
                amount = None

            self.patmatch.append((transtype, desc_pat, desc_exact,
                                  cat, freq, amount))

    def categorize_schwab(self, row):
        categorized = False

        for transtype, pat, exact, cat, freq, amount in self.patmatch:
            if transtype:
                if transtype != row['Type']:
                    continue
            elif exact:
                if row['Description'] != exact:
                    continue
            elif pat:
                if not re.search(pat, row['Description']):
                    continue
            else:
                assert "not expected"

            if amount is not None:
                if float(amount) < 0:
                    if dollar_str_to_val(row['Withdrawal (-)']) == '':
                        continue
                    if -float(amount)\
                       != float(dollar_str_to_val(row['Withdrawal (-)'])):
                        continue
                else:
                    assert "only matching on withdrawals"
            # found a match
            row['Category'] = cat
            assert cat != 'null' and cat != ''
            if freq:
                row['Frequency'] = freq
            print("===>", row['Category'],
                  row.get('Frequency', "no frequency"))
            categorized = True
            break

        if not categorized:
            print("Uncategorized", row)

        return categorized

    def categorize(self, row):
        categorized = False

        for transtype, pat, exact, cat, freq, amount in self.patmatch:
            if transtype:
                # not considering for credit card
                continue
            elif exact:
                if row['Description'] != exact:
                    continue
            elif pat:
                if not re.search(pat, row['Description']):
                    continue
            else:
                assert "not expected"

            # found a match
            assert not amount   # not matching on amount for now
            row['Category'] = cat
            assert cat != 'null' and cat != ''
            if freq:
                row['Frequency'] = freq
            print("===>", row['Category'],
                  row.get('Frequency', "no frequency"))
            categorized = True
            break

        if not categorized:
            print("Uncategorized", row)

        return categorized


class SchwabSheet(sync_google_spreadsheet.sheet_adapter.SheetAdapter):
    """
    General base class for finance spreadsheet.  There are a couple of
    individual sheets that have different columns
    """

    def __init__(self, sheet_adapter,
                 start_row_for_merging
                 ):
        def rowkey(row):
            withdrawal = dollar_str_to_val(row['Withdrawal (-)'])
            deposit = dollar_str_to_val(row['Deposit (+)'])

            key = "%s-%s-%s-%s" % (
                mdy_dt(row['Date']),
                withdrawal,
                deposit,
                row['Description'])
            return key

        super(SchwabSheet, self).__init__(sheet_adapter,
                                          start_row_for_merging,
                                          rowkey, non_empty_column='Date')


class ChaseSheet(sync_google_spreadsheet.sheet_adapter.SheetAdapter):
    """
    General base class for finance spreadsheet.  There are a couple of
    individual sheets that have different columns
    """

    def __init__(self, sheet_adapter,
                 start_row_for_merging
                 ):
        def rowkey(rowdict):
            key = "%s-%s-%f-%s" % (
                mdy_dt(rowdict['Trans Date']),
                mdy_dt(rowdict['Post Date']),
                float(rowdict['Amount']),
                rowdict['Description']
                )
            return key

        super(ChaseSheet, self).__init__(sheet_adapter,
                                         start_row_for_merging,
                                         rowkey, non_empty_column='Trans Date')


@click.group()
def main():
    pass

# TODO: sort_by_* could be merged/generalized


def sort_by_date(x, y):
    return cmp(mdy_dt(x['Date']), mdy_dt(y['Date']))


def sort_by_trans_date(x, y):
    try:
        return cmp(mdy_dt(x['Trans Date']), mdy_dt(y['Trans Date']))
    except Exception as e:
        print("couldn't parse out", x)
        print("couldn't parse out", y)
        raise e


def csv_streamer(fn, row_sort, skip_before_header, skip_after_header):
    new_rows = []
    with open(fn, "r") as f:
        if skip_before_header:
            f.readline()
        reader = csv.DictReader(f)

        for row in reader:
            # this can be elevated to a parameter.
            if skip_after_header:
                skip_after_header = False
                continue
            for k in row:
                if row[k] == 'null':
                    row[k] = ''
            new_rows.append(row)
    new_rows = sorted(new_rows, cmp=row_sort)
    for row in new_rows:
        yield row


def init_common(sync_config):
    with open(os.path.expanduser("~/.secrets-finance.yaml"), "r") as f:
        secrets = yaml.load(f)
    SCOPE = ["https://spreadsheets.google.com/feeds"]
    SECRETS_FILE = os.path.expanduser(secrets['sheet']['secrets_file'])
    SPREADSHEET = secrets['sheet']['name']
    credentials = ServiceAccountCredentials \
        .from_json_keyfile_name(SECRETS_FILE, SCOPE)
    # Authenticate using the signed key
    gss_client = gspread.authorize(credentials)
    gss = gss_client.open(SPREADSHEET)
    sheet = gss.worksheet(secrets[sync_config]['worksheet_name'])
    categorizer_sheet = \
        gss.worksheet(secrets[sync_config]['categorization_sheet'])
    categorizer = CategorizerSheet(categorizer_sheet)

    return secrets, sheet, categorizer


def update_schwab(sync_config):
    secrets, gss, categorizer = init_common(sync_config)

    sheet = SchwabSheet(gss, secrets[sync_config]['start_row'])
    sheet.load()
    ignore_before = mdy_dt(secrets[sync_config]['ignore_merge_dates_before'])

    # TODO: below could be generalized/parameterized
    # this is the generic logic
    s = None
    for fn in glob.glob(secrets[sync_config]['csvfile_pattern']):
        if s is not None:
            raise Exception("can't handle multiple files")
        s = csv_streamer(fn, sort_by_date,
                         skip_before_header=True, skip_after_header=True)

    uncategorized = []

    def annotate(row):
        if not categorizer.categorize_schwab(row):
            uncategorized.append(row)
        return row

    for row in s:
        if mdy_dt(row['Date']) < ignore_before:
            continue

        print(row)
        row = annotate(row)
        if not sheet.has(row):
            sheet.append(row)

    if len(uncategorized) > 0:
        print("========= Uncategorized =====")
        for row in uncategorized:
            print(row)

    sheet.sync()


@main.command()
def update_schwab_business():
    update_schwab('schwab_business')


@main.command()
def update_schwab_personal():
    update_schwab('schwab_personal')


@main.command()
def update_chase():
    secrets, gss, categorizer = init_common('chase')
    sync_config = 'chase'

    sheet = ChaseSheet(gss, secrets[sync_config]['start_row'])
    sheet.load()

    uncategorized = []

    def annotate(row):
        if not categorizer.categorize_schwab(row):
            uncategorized.append(row)
        return row

    # TODO: below could be generalized/parameterized
    # This is the generic logic
    s = None
    for fn in glob.glob(secrets[sync_config]['csvfile_pattern']):
        if s is not None:
            raise Exception("can't handle multiple files")
        s = csv_streamer(fn, sort_by_trans_date,
                         skip_before_header=False, skip_after_header=False)

    for row in s:
        print(row)
        row = annotate(row)
        if not sheet.has(row):
            sheet.append(row)

    print("========= Uncategorized =====")
    for row in uncategorized:
        print(row)

    sheet.sync()


if __name__ == "__main__":
    main()
