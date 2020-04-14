#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import logging
import sys

import requests
import xlrd

logger = logging.getLogger('luigi-interface')

# This dict maps 'report_types' to 'REPORT_IDS'
# Data sheets that don't require a report to be generated or
# refreshed have ids <= 0
# key format: 'type_timespan' (e.g. 'customers_7days')
REPORT_IDS = {
    'customers_1day': 1364,
    'customers_7days': 1379,

    'orders_7days': 1188,
    'orders_1day': 1246,

    'entries_1day': 1262,

    'bookings_7days': 0,
    'bookings_1month': -3,
    'bookings_1year': -1,
    'bookings_nextYear': -5,
    'bookings_all': -11,

    'guides': -2
}
REPORT_IDS_INV = {v: k for k, v in REPORT_IDS.items()}


def parse_arguments(args):
    parser = argparse.ArgumentParser(
        description="Refresh and fetch reports from go~mus")
    report_group = parser.add_mutually_exclusive_group(required=True)

    report_group.add_argument(
        '-i',
        '--report-id',
        type=int,
        help='ID of the report',
        choices=REPORT_IDS.values())
    report_group.add_argument(
        '-t',
        '--report-type',
        type=str,
        help='Type of the report',
        choices=REPORT_IDS.keys())
    parser.add_argument(
        'action',
        type=str,
        help='Action to take',
        choices=[
            'refresh',
            'fetch'],
        nargs='?',
        default='fetch')
    parser.add_argument(
        '-s',
        '--session-id',
        type=str,
        help='Session ID to use for authentication',
        required=True)

    parser.add_argument(
        '-I',
        '--sheet-index',
        type=int,
        help="Excel sheet page number",
        default=0)

    parser.add_argument(
        '-o',
        '--output-file',
        type=str,
        help='Name of Output file (for fetching)')

    parser.add_argument(
        '-l',
        '--luigi',
        help='Set true if run as part of a Luigi task',
        action='store_true')

    return parser.parse_args(args)


def parse_timespan(timespan, today=dt.datetime.today()):
    end_time = today - dt.timedelta(days=1)
    if timespan == '7days':
        # grab everything from yesterday till a week before
        start_time = end_time - dt.timedelta(weeks=1)
    elif timespan == '1month':
        start_time = end_time - dt.timedelta(days=30)
    elif timespan == '1year':
        start_time = end_time - dt.timedelta(days=365)
    elif timespan == '1day':
        start_time = end_time
    elif timespan == 'nextYear':
        start_time = end_time
        end_time = end_time + dt.timedelta(days=365)
    elif timespan == 'all':
        start_time = today - dt.timedelta(days=365*5)
        end_time = today + dt.timedelta(days=365*2)
    else:
        start_time = dt.date.min  # check this for error handling
    return start_time, end_time


def direct_download_url(base_url, report, timespan):
    start_time, end_time = parse_timespan(timespan)
    base_return = base_url + f'/{report}.xlsx'

    if not start_time == dt.date.min:
        # timespan is valid
        end_time = end_time.strftime("%Y-%m-%d")
        start_time = start_time.strftime("%Y-%m-%d")
        logger.info(f"Requesting report for timespan "
                    f"from {start_time} to {end_time}")
        return base_return + f'?end_at={end_time}&start_at={start_time}'

    return base_return


def get_request(url, sess_id):
    cookies = dict(_session_id=sess_id)
    response = requests.get(url, cookies=cookies)
    response.raise_for_status()
    if response.ok:
        logger.info("HTTP request successful")

    return response.content


def csv_from_excel(xlsx_content, target_csv, sheet_index):
    workbook = xlrd.open_workbook(file_contents=xlsx_content)
    sheet = workbook.sheet_by_index(sheet_index)
    writer = csv.writer(target_csv, quoting=csv.QUOTE_NONNUMERIC)
    for row_num in range(sheet.nrows):
        writer.writerow(sheet.row_values(row_num))


def request_report(args=sys.argv[1:]):
    args = parse_arguments(args)
    if args.report_id:
        report_id = args.report_id
    else:
        try:
            report_id = REPORT_IDS[args.report_type]
        except KeyError:  # should never happen because of argparse choices
            raise ValueError(
                f"Report type '{args.report_type}' not supported!")

    base_url = 'https://barberini.gomus.de'
    report_parts = REPORT_IDS_INV[report_id].split("_")

    logger.info(f"Working with report '{report_parts[0]}.xlsx'")

    # Work with the kind of report that is generated and maintained
    if report_id > 0:
        base_url += f'/admin/reports/{report_id}'

        if args.action == 'refresh':
            logger.info("Refreshing report")
            url = base_url + '/refresh'

        elif args.action == 'fetch':
            logger.info("Fetching report")
            url = base_url + '.xlsx'

    else:  # Work with the kind of report that is requested directly
        logger.info("Directly downloading report")
        if len(report_parts) < 2:
            timespan = ''
        else:
            timespan = report_parts[1]

        url = direct_download_url(base_url, report_parts[0], timespan)

    res_content = get_request(url, args.session_id)

    if args.action == 'fetch':
        if not args.luigi:
            filename = args.output_file
            if not filename:
                filename = REPORT_IDS_INV[report_id] + '.csv'
            with open(filename, 'w', encoding='utf-8') as csv_file:
                csv_from_excel(res_content, csv_file, args.sheet_index)
            logger.info(f'Saved report to file "{filename}"')
        else:
            logger.info("Running as Luigi task, returning response content")
            return res_content


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    request_report()
