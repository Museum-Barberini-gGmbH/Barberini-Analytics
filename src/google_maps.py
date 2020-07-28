import json
import sys

import googleapiclient.discovery
import luigi
import oauth2client.client
import pandas as pd
from oauth2client.file import Storage

from _utils import CsvToDb, DataPreparationTask, logger


class GoogleMapsReviewsToDb(CsvToDb):

    table = 'google_maps_review'

    def requires(self):

        return FetchGoogleMapsReviews()


class FetchGoogleMapsReviews(DataPreparationTask):

    # secret_files is a folder mounted from
    # /etc/barberini-analytics/secrets via docker-compose
    token_cache = luigi.Parameter(
        default='secret_files/google_gmb_credential_cache.json')
    client_secret = luigi.Parameter(
        default='secret_files/google_gmb_client_secret.json')
    is_interactive = luigi.BoolParameter(default=sys.stdin.isatty())
    scopes = ['https://www.googleapis.com/auth/business.manage']
    google_gmb_discovery_url = ('https://developers.google.com/my-business/'
                                'samples/mybusiness_google_rest_v4p5.json')

    api_service_name = 'mybusiness'
    api_version = 'v4'

    stars_dict = dict({  # google returns rating as a string
        'STAR_RATING_UNSPECIFIED': None,
        'ONE': 1,
        'TWO': 2,
        'THREE': 3,
        'FOUR': 4,
        'FIVE': 5
    })

    def output(self):

        return luigi.LocalTarget(
            f'{self.output_dir}/google_maps_reviews.csv',
            format=luigi.format.UTF8
        )

    def run(self) -> None:

        logger.info("loading credentials...")
        credentials = self.load_credentials()
        logger.info("creating service...")
        service = self.load_service(credentials)
        logger.info("fetching reviews...")
        raw_reviews = self.fetch_raw_reviews(service)
        logger.info("extracting reviews...")
        reviews_df = self.extract_reviews(raw_reviews)
        logger.info("success! writing...")

        with self.output().open('w') as output_file:
            reviews_df.to_csv(output_file, index=False)

    """
    uses oauth2 to authenticate with google, also caches credentials
    requires no login action if you have a valid cache
    """
    def load_credentials(self) -> oauth2client.client.Credentials:

        storage = Storage(self.token_cache)
        credentials = storage.get()

        # Access token missing or invalid, we need to require a new one
        if credentials is None:
            if not self.is_interactive:
                raise Exception(
                    ("ERROR: No valid credentials for google maps access and "
                     "no interactive shell to perform login, aborting!"))
            with open(self.client_secret) as client_secret:
                secret = json.load(client_secret)['installed']
            flow = oauth2client.client.OAuth2WebServerFlow(
                secret['client_id'],
                secret['client_secret'],
                self.scopes,
                secret['redirect_uris'][0])
            authorize_url = flow.step1_get_authorize_url()
            logger.warning("Go to the following link in your browser: "
                           f"{authorize_url}")
            code = input("Enter verification code: ").strip()
            credentials = flow.step2_exchange(code)
            storage.put(credentials)

        return credentials

    def load_service(self, credentials) -> googleapiclient.discovery.Resource:

        return googleapiclient.discovery.build(
            self.api_service_name,
            self.api_version,
            credentials=credentials,
            discoveryServiceUrl=self.google_gmb_discovery_url)

    """
    The GMB API is based on resources that contain other resources.
    An authenticated user has account(s), an accounts contains locations, and
    a location contains reviews (which we need to request one by one).
    """
    def fetch_raw_reviews(self, service, page_size=100):
        # get account identifier
        account_list = service.accounts().list().execute()
        # in almost all cases one only has access to one account
        account = account_list['accounts'][0]['name']

        # get location identifier of the first location
        # available to this account
        # it seems like this identifier is unique per user
        location_list = service.accounts().locations()\
            .list(parent=account).execute()
        if len(location_list['locations']) == 0:
            raise Exception(
                ("ERROR: This user seems to not have access to any google "
                 "location, unable to fetch reviews"))
        location = location_list['locations'][0]['name']
        place_id = location_list['locations'][0]['locationKey']['placeId']

        # get reviews for that location
        review_list = service.accounts().locations().reviews().list(
            parent=location,
            pageSize=page_size).execute()
        yield from [
            {**review, 'placeId': place_id}
            for review
            in review_list['reviews']
        ]
        total_reviews = review_list['totalReviewCount']

        pbar_loop = iter(self.tqdm(
            range(total_reviews),
            desc="Fetching Google Maps pages"
        ))
        while 'nextPageToken' in review_list:
            next_page_token = review_list['nextPageToken']
            # TODO: optimize by requesting the latest review from DB rather
            # than fetching more pages once that one is found
            review_list = service.accounts().locations().reviews().list(
                parent=location,
                pageSize=page_size,
                pageToken=next_page_token).execute()
            for review in review_list['reviews']:
                next(pbar_loop)
            yield from [
                {**review, 'placeId': place_id}
                for review
                in review_list['reviews']
            ]

            if self.minimal_mode:
                review_list.pop('nextPageToken')

    def extract_reviews(self, raw_reviews) -> pd.DataFrame:

        extracted_reviews = []
        for raw in raw_reviews:
            extracted = dict()
            extracted['google_maps_review_id'] = raw['reviewId']
            extracted['post_date'] = raw['createTime']
            extracted['rating'] = self.stars_dict[raw['starRating']]
            extracted['text'] = None
            extracted['text_english'] = None
            extracted['language'] = None
            extracted['place_id'] = raw['placeId']

            raw_comment = raw.get('comment', None)
            if raw_comment:
                # this assumes possibly unintended behavior of Google's API
                # see for details:
                # https://gitlab.hpi.de/bp-barberini/bp-barberini/issues/79
                # We want to keep both original and english translation)

                # english reviews are as is; (Original) may be part of the text
                if "(Translated by Google)" not in raw_comment:
                    extracted['text'] = raw_comment
                    extracted['text_english'] = raw_comment
                    extracted['language'] = "english"

                # other reviews have this format:
                #   (Translated by Google)[english translation]\n\n
                #   (Original)\n[original review]
                else:
                    extracted['text'] = raw_comment.split(
                        "(Original)")[1].strip()
                    extracted['text_english'] = raw_comment.split(
                        "(Original)")[0].split(
                        "(Translated by Google)")[1].strip()
                    extracted['language'] = "other"

            extracted_reviews.append(extracted)
        return pd.DataFrame(extracted_reviews)
