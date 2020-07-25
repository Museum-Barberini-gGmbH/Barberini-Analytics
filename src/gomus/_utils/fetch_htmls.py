import datetime as dt
import os
import time

import luigi
import pandas as pd
import requests
from luigi.format import UTF8

from _utils import DataPreparationTask
from ..orders import OrdersToDb
from .extract_bookings import ExtractGomusBookings


class FetchGomusHTML(DataPreparationTask):
    url = luigi.parameter.Parameter(description="The URL to fetch")

    def output(self):
        name = f'{self.output_dir}/gomus/html/' + \
            self.url. \
            replace('http://', ''). \
            replace('https://', ''). \
            replace('/', '_'). \
            replace('.', '_') + \
            '.html'

        return luigi.LocalTarget(name, format=UTF8)

    # simply wait for a moment before requesting, as we don't want to
    # overwhelm the server with our interest in classified information...
    def run(self):
        time.sleep(0.2)
        response = requests.get(
            self.url,
            cookies=dict(
                _session_id=os.environ['GOMUS_SESS_ID']))
        response.raise_for_status()

        with self.output().open('w') as html_out:
            html_out.write(response.text)


class FetchBookingsHTML(DataPreparationTask):
    timespan = luigi.parameter.Parameter(default='_nextYear')
    base_url = luigi.parameter.Parameter(
        description="Base URL to append bookings IDs to")
    columns = luigi.parameter.ListParameter(description="Column names")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_list = []

    def requires(self):
        return ExtractGomusBookings(
            timespan=self.timespan, columns=self.columns)

    def output(self):
        return luigi.LocalTarget(
            f'{self.output_dir}/gomus/bookings_htmls.txt')

    def run(self):
        with self.input().open('r') as input_file:
            bookings = pd.read_csv(input_file)

            if self.minimal_mode:
                bookings = bookings.head(5)

        today_time = dt.datetime.today() - dt.timedelta(weeks=5)
        db_booking_rows = self.db_connector.query(f'''
            SELECT booking_id FROM gomus_booking
            WHERE start_datetime < '{today_time}'
        ''')

        for i, row in bookings.iterrows():
            booking_id = row['booking_id']

            booking_in_db = False
            for db_row in db_booking_rows:
                if db_row[0] == booking_id:
                    booking_in_db = True
                    break

            if not booking_in_db:
                booking_url = self.base_url + str(booking_id)

                html_target = yield FetchGomusHTML(url=booking_url)
                self.output_list.append(html_target.path)

        with self.output().open('w') as html_files:
            html_files.write('\n'.join(self.output_list))


class FetchOrdersHTML(DataPreparationTask):
    base_url = luigi.parameter.Parameter(
        description="Base URL to append order IDs to")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_list = []
        self.order_ids = []

    def requires(self):
        return OrdersToDb()

    def output(self):
        return luigi.LocalTarget(
            f'{self.output_dir}/gomus/orders_htmls.txt')

    def get_order_ids(self):

        order_ids = []

        query_limit = 'LIMIT 10' if self.minimal_mode else ''

        order_ids = self.db_connector.query(f'''
            SELECT a.order_id
            FROM gomus_order AS a
            LEFT OUTER JOIN gomus_order_contains AS b
            ON a.order_id = b.order_id
            WHERE ticket IS NULL
            {query_limit}
        ''')

        return order_ids

    def run(self):
        self.order_ids = [order_id[0] for order_id in self.get_order_ids()]

        for i in range(len(self.order_ids)):

            url = self.base_url + str(self.order_ids[i])

            html_target = yield FetchGomusHTML(url=url)
            self.output_list.append(html_target.path)

        with self.output().open('w') as html_files:
            html_files.write('\n'.join(self.output_list))
