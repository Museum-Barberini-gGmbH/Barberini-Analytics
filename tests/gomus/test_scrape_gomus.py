import unittest
from unittest.mock import patch
from luigi.mock import MockTarget
from luigi.format import UTF8

import pandas as pd
import mmh3
import sys

from gomus._utils.scrape_gomus import\
    EnhanceBookingsWithScraper,\
    FetchBookingsHTML,\
    FetchGomusHTML
from gomus._utils.extract_bookings import ExtractGomusBookings


class TestEnhanceBookingsWithScraper(unittest.TestCase):
    '''
    This test gets a set of booking-IDs (in test_data/scrape_bookings_data.csv)
    and downloads their actual HTML-files.
    It then compares the expected hash (also in the file above)
    with the hash of what our scraper got.

    To easily add test cases, use create_test_data_for_bookings.py.'''

    hash_seed = 666

    @patch.object(ExtractGomusBookings, 'output')
    @patch.object(FetchBookingsHTML, 'output')
    @patch.object(EnhanceBookingsWithScraper, 'output')
    def test_scrape_bookings(self,
                             output_mock,
                             all_htmls_mock,
                             input_mock):

        test_data = pd.read_csv(
            'tests/test_data/gomus/scrape_bookings_data.csv')
        # we generate random stuff for extracted_bookings,
        # because the scraper doesn't need it for any calculations
        test_data.insert(1, 'some_other_value', test_data.index)

        extracted_bookings = test_data.filter(
            ['booking_id',
             'some_other_value'])

        input_target = MockTarget('extracted_bookings_out', format=UTF8)
        input_mock.return_value = input_target
        with input_target.open('w') as input_file:
            extracted_bookings.to_csv(input_file, index=False)

        # download htmls (similar to what FetchBookingsHTML does)
        html_file_names = []
        for i, row in extracted_bookings.iterrows():
            booking_id = row['booking_id']
            new_html_task = FetchGomusHTML(
                url=f"https://barberini.gomus.de/admin/bookings/{booking_id}")
            new_html_task.run()
            html_file_names.append(new_html_task.output().path)

        all_htmls_target = MockTarget('bookings_htmls_out', format=UTF8)
        all_htmls_mock.return_value = all_htmls_target
        with all_htmls_target.open('w') as all_htmls_file:
            all_htmls_file.write('\n'.join(html_file_names))

        output_target = MockTarget('enhanced_bookings_out', format=UTF8)
        output_mock.return_value = output_target

        EnhanceBookingsWithScraper().run()

        expected_output = test_data.filter(
            ['booking_id',
             'some_other_value',
             'expected_hash'])

        with output_target.open('r') as output_file:
            actual_output = pd.read_csv(output_file)

        self.assertEqual(len(expected_output.index), len(actual_output.index))

        for i in range(len(actual_output)):
            expected_row = expected_output.iloc[i]
            actual_row = actual_output.iloc[i]

            # test if order stayed the same
            self.assertEqual(
                expected_row['booking_id'],
                actual_row['booking_id'])

            # test if existing data got modified
            self.assertEqual(
                expected_row['some_other_value'],
                actual_row['some_other_value'])

            # test if scraped data is correct
            hash_str = ','.join([
                str(actual_row['customer_id']),
                str(actual_row['order_date']),
                str(actual_row['language'])])
            actual_hash = mmh3.hash(hash_str, seed=self.hash_seed)
            self.assertEqual(
                actual_hash,
                expected_row['expected_hash'],
                msg=f"Scraper got wrong values:\n\
{str(actual_row) if sys.stdin.isatty() else 'REDACTED ON NON-TTY'}")
