import os
from typing import Callable, Dict, Iterable, List, Tuple, TypeVar, Union

import psycopg2

import _utils
logger = _utils.logger

T = TypeVar('T')
TQueryAndArgs = Tuple[
    str,
    Union[Iterable[object], Dict[str, object]]
]


class DbConnector:

    def __init__(self, host, user, database, password):

        super().__init__()
        self.host = host
        self.user = user
        self.database = database
        self.password = password

    @property
    def database(self):

        return self.__database

    @database.setter
    def database(self, database):

        # crucial to avoid unintended access to default postgres database
        assert database, "Database was not specified"
        self.__database = database

    def __repr__(self):

        return (
            f'{type(self).__name__}('
            f'host={self.host}, '
            f'user={self.user}, '
            f'database={self.database})'
        )

    def __str__(self):

        return f'{type(self).__name__}(db={self.database})'

    def execute(
                self,
                *queries: List[Union[str, TQueryAndArgs]]
            ) -> List[Tuple]:
        """
        Execute one or multiple queries as one atomic operation and returns
        the results of all queries. If any query fails, all will be reverted
        and an error will be raised.
        """

        return list(self._execute_queries(
            queries_and_args=queries,
            result_function=lambda cur: None
        ))

    def exists(self, query: str) -> bool:
        """
        Check if the given query returns any results. Return
        True if the query returns results, otherwise False.
        Note that the given query should absolutely not end on a semicolon.
        """

        return bool(self.query(
            query=f'SELECT EXISTS({query})',
            only_first=True)[0])

    def exists_table(self, table: str) -> bool:
        """
        Check if the given table is present in the database.
        """

        return self.exists(f'''
                SELECT * FROM information_schema.tables
                WHERE LOWER(table_name) = LOWER('{table}')
            ''')

    def query(
                self,
                query: str,
                *args: Iterable[object],
                only_first: bool = False,
                **kwargs: Dict[str, object]
            ) -> List[Tuple]:
        """
        Execute a query and return a list of results.
        If only_first is set to True, only return the
        first result as a tuple.
        """

        def result_function(cursor):
            nonlocal only_first
            if only_first:
                return cursor.fetchone()
            return cursor.fetchall()

        results = self._execute_query(
            query=query,
            result_function=result_function,
            args=args,
            kwargs=kwargs
        )
        result = next(results)
        if next(results, result) is not result:
            raise AssertionError(
                "DB access with just one query should only return one result")
        return result

    def query_with_header(
                self,
                query: str,
                *args: Iterable[object],
                **kwargs: Dict[str, object]
            ) -> List[Tuple]:
        """
        Execute a query and return two values of which the first is the list
        of fetched rows and the second is the list of column names.
        """

        all_results = self._execute_query(
            query=query,
            result_function=lambda cursor:
                (cursor.fetchall(), [desc[0] for desc in cursor.description]),
            args=args,
            kwargs=kwargs
        )
        results = next(all_results)
        if next(all_results, results) is not results:
            raise AssertionError(
                "DB access with just one query should only return one table")
        return results

    def _create_connection(self):

        return psycopg2.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password
        )

    def _execute_queries(
                self,
                queries_and_args: List[Union[str, TQueryAndArgs]],
                result_function: Callable[[psycopg2.extensions.cursor], T]
            ) -> List[T]:
        """
        Executes all passed queries as one atomic operation and yields the
        results of each query. If any query fails, all will be reverted and an
        error will be raised.
        Note that this is a generator function so the operation will be only
        commited once the generator has been enumerated.
        """

        conn = self._create_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    for query_and_args in queries_and_args:
                        query, args = \
                            query_and_args \
                            if isinstance(query_and_args, tuple) \
                            else (query_and_args, ())
                        logger.debug(
                            "DbConnector: Executing query '''%s''' "
                            "with args: %s",
                            query,
                            args
                        )
                        try:
                            cur.execute(query, args)
                        except psycopg2.Error:
                            print(query, args)
                            raise
                        yield result_function(cur)
                for notice in conn.notices:
                    logger.warning(notice.strip())
        finally:
            conn.close()

    def _execute_query(
                self,
                query: str,
                result_function: Callable[[psycopg2.extensions.cursor], T],
                args: Iterable[object] = (),
                kwargs: Dict[str, object] = {}
            ) -> None:
        """
        Executes the passed query and returns the results.
        Note that this is a generator function so the operation will be only
        commited once the generator has been enumerated.
        """

        assert not args or not kwargs, "cannot combine args and kwargs"
        all_args = next(
            filter(bool, [args, kwargs]),
            # always pass args for consistent
            # resolution of percent escapings
            None
        )

        return self._execute_queries([(query, all_args)], result_function)


def db_connector(database=None):

    connector = default_connector()
    if database is None:
        database = os.environ['POSTGRES_DB']
    connector.database = database
    return connector


def default_connector():

    return DbConnector(
        host=os.environ['POSTGRES_HOST'],
        database='postgres',
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'])


def register_array_type(type_name, namespace_name):
    """
    Register the specified postgres type manually, allowing psycopg2 to parse
    arrays of that type correctly.
    If custom types are not configured, queries such as
        c.query("select array ['pg_type'::information_schema.sql_identifier]")
    will be answered with strings like '{pg_type}' rather than with a true
    array of objects.
    """

    connector = default_connector()
    typarray, typcategory = connector.query(
        '''
            SELECT typarray, typcategory
            FROM pg_type
            JOIN pg_namespace
                ON typnamespace = pg_namespace.oid
            WHERE typname ILIKE %(type_name)s
                AND nspname ILIKE %(namespace_name)s
        ''',
        only_first=True,
        type_name=type_name,
        namespace_name=namespace_name
    )
    psycopg2.extensions.register_type(
        psycopg2.extensions.new_array_type(
            (typarray,),
            f'{type_name}[]',
            {'S': psycopg2.STRING}[typcategory]
        ))
