import datetime as dt
import luigi
import os
import pandas as pd
import psycopg2
import requests
import time
from luigi.format import UTF8

from gomus.orders import OrdersToDB
from gomus._utils.extract_bookings import ExtractGomusBookings
from set_db_connection_options import set_db_connection_options


class FetchGomusHTML(luigi.Task):
    url = luigi.parameter.Parameter(description="The URL to fetch")

    def output(self):
        name = 'output/gomus/html/' + \
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


class FetchBookingsHTML(luigi.Task):
    timespan = luigi.parameter.Parameter(default='_nextYear')
    base_url = luigi.parameter.Parameter(
        description="Base URL to append bookings IDs to")
    minimal = luigi.parameter.BoolParameter(default=False)
    columns = luigi.parameter.ListParameter(description="Column names")

    host = None
    database = None
    user = None
    password = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_db_connection_options(self)
        self.output_list = []

    def requires(self):
        return ExtractGomusBookings(timespan=self.timespan,
                                    minimal=self.minimal,
                                    columns=self.columns)

    def output(self):
        return luigi.LocalTarget('output/gomus/bookings_htmls.txt')

    def run(self):
        with self.input().open('r') as input_file:
            bookings = pd.read_csv(input_file)

            if self.minimal:
                bookings = bookings.head(5)

        db_booking_rows = []

        try:
            conn = psycopg2.connect(
                host=self.host, database=self.database,
                user=self.user, password=self.password
            )

            cur = conn.cursor()

            cur.execute("SELECT EXISTS(SELECT * FROM information_schema.tables"
                        f" WHERE table_name=\'gomus_booking\')")

            today_time = dt.datetime.today() - dt.timedelta(weeks=5)
            if cur.fetchone()[0]:
                query = (f'SELECT booking_id FROM gomus_booking'
                         f' WHERE start_datetime < \'{today_time}\'')

                cur.execute(query)
                db_booking_rows = cur.fetchall()

        finally:
            if conn is not None:
                conn.close()

        for i, row in bookings.iterrows():
            booking_id = row['booking_id']

            booking_in_db = False
            for db_row in db_booking_rows:
                if db_row[0] == booking_id:
                    booking_in_db = True
                    break

            if not booking_in_db:
                booking_url = self.base_url + str(booking_id)

                html_target = yield FetchGomusHTML(booking_url)
                self.output_list.append(html_target.path)

        with self.output().open('w') as html_files:
            html_files.write('\n'.join(self.output_list))


class FetchOrdersHTML(luigi.Task):
    minimal = luigi.parameter.BoolParameter(default=False)
    base_url = luigi.parameter.Parameter(
        description="Base URL to append order IDs to")

    host = None
    database = None
    user = None
    password = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_db_connection_options(self)
        self.output_list = []
        self.order_ids = [order_id[0] for order_id in self.get_order_ids()]

    def requires(self):
        return OrdersToDB(minimal=self.minimal)

    def output(self):
        return luigi.LocalTarget('output/gomus/orders_htmls.txt')

    def get_order_ids(self):
        try:
            conn = psycopg2.connect(
                host=self.host, database=self.database,
                user=self.user, password=self.password
            )
            cur = conn.cursor()
            query_limit = 'LIMIT 10' if self.minimal else ''

            cur.execute("SELECT EXISTS(SELECT * FROM information_schema.tables"
                        f" WHERE table_name=\'gomus_order_contains\')")
            if cur.fetchone()[0]:
                query = (f'SELECT order_id FROM gomus_order WHERE order_id '
                         f'NOT IN (SELECT order_id FROM '
                         f'gomus_order_contains) {query_limit}')
                cur.execute(query)
                order_ids = cur.fetchall()

            else:
                query = (f'SELECT order_id FROM gomus_order {query_limit}')

            return order_ids

        finally:
            if conn is not None:
                conn.close()

    def run(self):
        for i in range(len(self.order_ids)):

            url = self.base_url + str(self.order_ids[i])

            html_target = yield FetchGomusHTML(url)
            self.output_list.append(html_target.path)

        with self.output().open('w') as html_files:
            html_files.write('\n'.join(self.output_list))
