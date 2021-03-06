"""Provides tasks for downloading all posts and associated information."""

import luigi

from apple_appstore import AppstoreReviewsToDb
from facebook import FbPostsToDb, FbPostCommentsToDb, FbPostPerformanceToDb
from google_maps import GoogleMapsReviewsToDb
from gplay import GooglePlaystoreReviewsToDb
from instagram import IgToDb, IgPostPerformanceToDb
from twitter import TweetsToDb, TweetPerformanceToDb, TweetAuthorsToDb


class PostsToDb(luigi.WrapperTask):
    """Download posts from all supported platforms."""

    fetch_performance = luigi.BoolParameter(
        description="If enabled, performance data will be also fetched now.",
        default=False
    )

    def requires(self):

        yield AppstoreReviewsToDb()
        yield FbPostsToDb()
        yield FbPostCommentsToDb()
        yield GoogleMapsReviewsToDb()
        yield GooglePlaystoreReviewsToDb()
        yield IgToDb()
        yield TweetAuthorsToDb()
        yield TweetsToDb()

        if self.fetch_performance:
            yield PostPerformanceToDb()


class PostPerformanceToDb(luigi.WrapperTask):
    """Download performance data about posts from all supported platforms."""

    def requires(self):
        yield FbPostPerformanceToDb()
        yield IgPostPerformanceToDb()
        yield TweetPerformanceToDb()
