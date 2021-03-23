"""Provides task to download all exhibitions and their times into the DB."""

from dateutil import parser as dateparser

import luigi
from luigi.format import UTF8
import pandas as pd
import requests

from _utils import CsvToDb, DataPreparationTask


class ExhibitionTimesToDb(CsvToDb):
    """Store all fetched exhibition times into the database."""

    table = 'exhibition_time'

    def _requires(self):

        return luigi.task.flatten([
            ExhibitionsToDb(),
            super()._requires()
        ])

    def requires(self):

        return FetchExhibitionTimes()


class ExhibitionsToDb(CsvToDb):
    """Store all fetched exhibitions into the database."""

    table = 'exhibition_raw'

    def requires(self):

        return FetchExhibitions()


class FetchExhibitions(DataPreparationTask):
    """Fetch all exhibitions from the Gomus API."""

    url = luigi.Parameter(
        default='https://barberini.gomus.de/api/v4/exhibitions?per_page=100'
    )

    def output(self):

        return luigi.LocalTarget(
            f'{self.output_dir}/gomus/exhibitions.csv',
            format=UTF8
        )

    def run(self):

        response = requests.get(self.url)
        response.raise_for_status()
        content = response.json()

        df = pd.DataFrame(self.extract_rows(content))

        with self.output().open('w') as output_file:
            df.to_csv(output_file, index=False, header=True)

    def extract_rows(self, content):

        return [
            self.extract_row(exhibition)
            for exhibition in content['exhibitions']
        ]

    def extract_row(self, exhibition):

        row = {'title': exhibition['title']}
        picture = exhibition.get('picture')
        if picture:
            original = picture.get('original')
            if original:
                row['picture_url'] = original
        return row


class FetchExhibitionTimes(FetchExhibitions):
    """Fetch all exhibition times from the Gomus API."""

    def requires(self):

        yield ExhibitionsToDb()

    def output(self):

        return luigi.LocalTarget(
            f'{self.output_dir}/gomus/exhibition_times.csv',
            format=UTF8
        )

    def extract_rows(self, content):

        return [
            row
            for exhibition in content['exhibitions']
            for row in self.extract_row(exhibition)
        ]

    def extract_row(self, exhibition):

        return [
            {
                'title': exhibition['title'],
                'start_date': dateparser.parse(time_frame['start_at']).date(),
                'end_date': dateparser.parse(time_frame['end_at']).date()
            }
            for time_frame
            in exhibition['time_frames']
        ]
