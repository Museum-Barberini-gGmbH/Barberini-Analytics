import csv
import os
import re
import logging

import dateparser
import luigi
import pandas as pd
from luigi.format import UTF8
from lxml import html

from data_preparation_task import DataPreparationTask
from gomus._utils.extract_bookings import ExtractGomusBookings
from gomus._utils.fetch_htmls import (FetchBookingsHTML, FetchGomusHTML,
                                      FetchOrdersHTML)
from gomus.customers import hash_id
from set_db_connection_options import set_db_connection_options

logger = logging.getLogger('luigi-interface')

# inherit from this if you want to scrape gomus (it might be wise to have
# a more general scraper class if we need to scrape something other than
# gomus)
class GomusScraperTask(DataPreparationTask):
    base_url = "https://barberini.gomus.de"

    host = None
    database = None
    user = None
    password = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_db_connection_options(self)

    def extract_from_html(self, base_html, xpath):
        # try:
        return html.tostring(base_html.xpath(
            xpath)[0], method='text', encoding="unicode")
        # except IndexError:
        #    return ""


class EnhanceBookingsWithScraper(GomusScraperTask):
    columns = luigi.parameter.ListParameter(description="Column names")
    timespan = luigi.parameter.Parameter(default='_nextYear')

    # could take up to an hour to scrape all bookings in the next year
    worker_timeout = 3600

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def requires(self):
        yield ExtractGomusBookings(timespan=self.timespan,
                                   columns=self.columns)
        yield FetchBookingsHTML(timespan=self.timespan,
                                base_url=self.base_url + '/admin/bookings/',
                                columns=self.columns)

    def output(self):
        return luigi.LocalTarget('output/gomus/bookings.csv', format=UTF8)

    def run(self):
        with self.input()[0].open('r') as input_file:
            bookings = pd.read_csv(input_file)

            if os.environ['MINIMAL'] == 'True':
                bookings = bookings.head(5)

        bookings.insert(1, 'customer_id', 0)  # new column at second position
        bookings.insert(len(bookings.columns), 'order_date', None)
        bookings.insert(len(bookings.columns), 'language', "")

        with self.input()[1].open('r') as all_htmls:
            for i, html_path in enumerate(all_htmls):
                html_path = html_path.replace('\n', '')
                with open(html_path,
                          'r',
                          encoding='utf-8') as html_file:
                    res_details = html_file.read()
                tree_details = html.fromstring(res_details)

                # firefox says the the xpath starts with //body/div[3]/ but we
                # apparently need div[2] instead
                booking_details = tree_details.xpath(
                    '//body/div[2]/div[2]/div[3]'
                    '/div[4]/div[2]/div[1]/div[3]')[0]

                # Order Date
                # .strip() removes \n in front of and behind string
                raw_order_date = self.extract_from_html(
                    booking_details,
                    'div[1]/div[2]/small/dl/dd[2]').strip()
                bookings.loc[i, 'order_date'] =\
                    dateparser.parse(raw_order_date)

                # Language
                bookings.loc[i, 'language'] = self.extract_from_html(
                    booking_details,
                    "div[contains(div[1]/dl[2]/dt/text(),'Sprache')]"
                    "/div[1]/dl[2]/dd").strip()

                try:
                    customer_details = tree_details.xpath(
                        '/html/body/div[2]/div[2]/div[3]/'
                        'div[4]/div[2]/div[2]/div[2]')[0]

                    # Customer E-Mail (not necessarily same as in report)
                    customer_mail = self.extract_from_html(
                        customer_details,
                        'div[1]/div[1]/div[2]/small[1]').strip().split('\n')[0]

                    if re.match(r'^\S+@\S+\.\S+$', customer_mail):
                        bookings.loc[i, 'customer_id'] = hash_id(customer_mail)

                except IndexError:  # can't find customer mail
                    bookings.loc[i, 'customer_id'] = 0

        bookings, invalid_values = self.ensure_foreign_keys(bookings)
        if invalid_values:  # fetch invalid E-Mail addresses anew
            for booking_id in invalid_values['booking_id']:
                self.scrape_new_mail(booking_id)

        with self.output().open('w') as output_file:
            bookings.to_csv(
                output_file,
                index=False,
                header=True,
                quoting=csv.QUOTE_NONNUMERIC)

    def scrape_new_mail(self, booking_id):
        logger.info(f"Fetching new mail for booking {booking_id}")
        # First step: Get customer of booking (cannot use customer_id,
        # since it has been derived from the wrong e-mail address)
        base_url = 'https://barberini.gomus.de/admin'
        booking_task = FetchGomusHTML(
            url=f'{base_url}/bookings/{booking_id}')
        yield booking_task
        with booking_task.output().open('r') as booking_html:
            booking_html = html.fromstring(booking_html.read())
            booking_details = booking_html.xpath(
                    '//body/div[2]/div[2]/div[3]'
                    '/div[4]/div[2]/div[1]/div[3]')[0]
            print(booking_details)

        customer_task = FetchGomusHTML(
            url=f'{base_url}/customers/{gomus_id}')
        yield customer_task
        with customer_task.output().open('r') as customer_html:
            # TODO: find e-mail entry
            pass

        # TODO: update gomus_to_customer_mapping to point gomus_id to new
        # customer_id

class ScrapeGomusOrderContains(GomusScraperTask):

    # 60 minutes until the task will timeout
    # set to about 800000 for collecting historic data ≈ 7 Days
    worker_timeout = 3600

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def requires(self):
        return FetchOrdersHTML(base_url=self.base_url + '/admin/orders/')

    def output(self):
        return luigi.LocalTarget(
            'output/gomus/scraped_order_contains.csv', format=UTF8)

    def run(self):

        order_details = []

        with self.input().open('r') as all_htmls:
            for i, html_path in enumerate(all_htmls):
                html_path = html_path.replace('\n', '')
                with open(html_path,
                          'r',
                          encoding='utf-8') as html_file:
                    res_order = html_file.read()

                tree_order = html.fromstring(res_order)

                tree_details = tree_order.xpath(
                    ('//body/div[2]/div[2]/div[3]/div[2]/div[2]/'
                     'div/div[2]/div/div/div/div[2]'))[0]

                # every other td contains the information of an article in the
                # order
                for article in tree_details.xpath(
                        # 'table/tbody[1]/tr[position() mod 2 = 1]'):
                        'table/tbody[1]/tr'):

                    new_article = dict()

                    # Workaround for orders like 671144
                    id_xpath = 'td[1]/div|td[1]/a/div|td[1]/a'
                    if len(article.xpath(id_xpath)) == 0:
                        continue

                    # excursions have a link there and sometimes no div
                    new_article["article_id"] = int(
                        self.extract_from_html(
                            article, id_xpath).strip())

                    order_id = int(re.findall(r'(\d+)\.html$', html_path)[0])
                    new_article["order_id"] = order_id

                    # Workaround for orders like 478531
                    # if td[3] has no child, we have nowhere to find the ticket
                    if len(article.xpath('td[3][count(*)>0]')) == 0:
                        continue
                    new_article["ticket"] = self.extract_from_html(
                        article, 'td[3]/strong').strip()

                    if new_article["ticket"] == '':
                        continue

                    infobox_str = html.tostring(
                        article.xpath('td[2]/div')[0],
                        method='text',
                        encoding="unicode")

                    # Workaround for orders like 679577
                    raw_date_re = re.findall(r'\d.*Uhr', infobox_str)
                    if not len(raw_date_re) == 0:
                        raw_date = raw_date_re[0]
                    else:
                        # we need something to mark an
                        # invalid / nonexistent date
                        raw_date = '1.1.1900'
                    new_article["date"] = dateparser.parse(raw_date)

                    new_article["quantity"] = int(
                        self.extract_from_html(article, 'td[4]'))

                    raw_price = self.extract_from_html(article, 'td[5]')
                    new_article["price"] = float(
                        raw_price.replace(
                            ",", ".").replace(
                            "€", ""))

                    order_details.append(new_article)

        df = pd.DataFrame(order_details)

        df, _ = self.ensure_foreign_keys(df)

        with self.output().open('w') as output_file:
            df.to_csv(output_file, index=False, quoting=csv.QUOTE_NONNUMERIC)
