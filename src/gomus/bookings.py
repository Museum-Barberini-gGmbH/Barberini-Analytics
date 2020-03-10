import datetime as dt

import luigi
import mmh3
import numpy as np
import pandas as pd
from luigi.format import UTF8

from csv_to_db import CsvToDb
from ensure_foreign_keys import ensure_foreign_keys
from gomus._utils.fetch_report import FetchGomusReport
from gomus._utils.scrape_gomus import EnhanceBookingsWithScraper
from gomus.customers import CustomersToDB, hash_id
from set_db_connection_options import set_db_connection_options


class BookingsToDB(CsvToDb):

    table = 'gomus_booking'

    columns = [
        ('booking_id', 'INT'),
        ('customer_id', 'INT'),
        ('category', 'TEXT'),
        ('participants', 'INT'),
        ('guide_id', 'INT'),
        ('duration', 'INT'),  # in minutes
        ('exhibition', 'TEXT'),
        ('title', 'TEXT'),
        ('status', 'TEXT'),
        ('start_datetime', 'TIMESTAMP'),
        ('order_date', 'DATE'),
        ('language', 'TEXT')
    ]

    primary_key = 'booking_id'

    foreign_keys = [
        {
            'origin_column': 'customer_id',
            'target_table': 'gomus_customer',
            'target_column': 'customer_id'
        }
    ]

    def requires(self):
        return EnhanceBookingsWithScraper(
            columns=[col[0] for col in self.columns],
            foreign_keys=self.foreign_keys)


class ExtractGomusBookings(luigi.Task):
    seed = luigi.parameter.IntParameter(
        description="Seed to use for hashing", default=666)
    foreign_keys = luigi.parameter.ListParameter(
        description="The foreign keys to be asserted")

    host = None
    database = None
    user = None
    password = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_db_connection_options(self)

    def _requires(self):
        return luigi.task.flatten([
            CustomersToDB(),
            super()._requires()
        ])

    def requires(self):
        return FetchGomusReport(report='bookings', suffix='_nextYear')

    def output(self):
        return luigi.LocalTarget(
            f'output/gomus/bookings_prepared.csv', format=UTF8)

    def run(self):
        df = pd.read_csv(next(self.input()).path)
        if not df.empty:
            df['Buchung'] = df['Buchung'].apply(int)
            df['E-Mail'] = df['E-Mail'].apply(hash_id)
            df['Teilnehmerzahl'] = df['Teilnehmerzahl'].apply(int)
            df['Guide'] = df['Guide'].apply(self.hash_guide)
            df['Startzeit'] = df.apply(
                lambda x: self.calculate_start_datetime(
                    x['Datum'], x['Uhrzeit von']), axis=1)
            df['Dauer'] = df.apply(
                lambda x: self.calculate_duration(
                    x['Uhrzeit von'], x['Uhrzeit bis']), axis=1)

            # order_date and language are added by scraper
        else:
            # manually append "Startzeit" and "Dauer" to ensure pandas
            # doesn't crash even though nothing will be added
            df['Startzeit'] = 0
            df['Dauer'] = 0

        df = df.filter(['Buchung',
                        'E-Mail',
                        'Angebotskategorie',
                        'Teilnehmerzahl',
                        'Guide',
                        'Dauer',
                        'Ausstellung',
                        'Titel',
                        'Status',
                        'Startzeit'])
        df.columns = [
            'booking_id',
            'customer_id',
            'category',
            'participants',
            'guide_id',
            'duration',
            'exhibition',
            'title',
            'status',
            'start_datetime']

        df = ensure_foreign_keys(
            df,
            self.foreign_keys,
            self.host,
            self.database,
            self.user,
            self.password)

        with self.output().open('w') as output_file:
            df.to_csv(output_file, header=True, index=False)

    def hash_guide(self, guide_name):
        if guide_name is np.NaN:  # np.isnan(guide_name):
            return 0  # 0 represents empty value
        guides = guide_name.lower().replace(' ', '').split(',')
        guide = guides[0]
        return mmh3.hash(guide, self.seed, signed=True)

    def calculate_start_datetime(self, date_str, time_str):
        return dt.datetime.strptime(f'{date_str} {time_str}',
                                    '%d.%m.%Y %H:%M')

    def calculate_duration(self, from_str, to_str):
        return (dt.datetime.strptime(to_str, '%H:%M') -
                dt.datetime.strptime(from_str, '%H:%M')).seconds // 60
