'''
Some conveniences for working with SQLite dababases
'''
from sqlite3 import dbapi2 as sqlite
from sqlite3.dbapi2 import DataError, DatabaseError, Error, IntegrityError, \
                             InterfaceError, InternalError, NotSupportedError, \
                             OperationalError, ProgrammingError

class UnwrapCursor(sqlite.Cursor):
    '''
    OK, I've had it with these never-ending unwrap statements,
    so I will try to build them into the cursor directly.
    '''
    def _unwrap(self, item):
        '''
        backend for both fetchvalues and fetchvalue
        '''
        assert len(item) == 1, 'method only handles singlet results'
        try:
            return item[0]                        # tuple or similar?
        except KeyError:
            try:                                  # assume dict
                return list(item.values())[0]
            except:
                raise TypeError("method only handles lists/tuples or mappings")


    def fetchvalues(self):
        lst = self.fetchall()
        return [self._unwrap(item) for item in lst]


    def fetchvalue(self):
        return self._unwrap(self.fetchone())


class SqliteDB(object):
    '''
    convenience wrapper around pysqlite
    '''
    db_path = ':memory:'            # default for testing
    text_factory = str

    cursor_class = UnwrapCursor

    pragmas = ["foreign_keys=on"]                     # required to make cascading deletes work
    connection_args = {'isolation_level':'immediate'} # None for autocommit,
                                                      # 'deferred', 'exclusive'

    def __init__(self, db_path=None):

        if db_path is not None:
            self.db_path = db_path
        self._db = None
        self._columns = {}
        self._row_dicts = True
        self._connection = self._cursor = None


    def _dict_factory(self, cursor, row):
        '''
        stolen from
        https://github.com/couchbase/pysqlite/blob/master/doc/includes
               /sqlite3/row_factory.py
        '''
        d = {}

        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]

        return d


    def get_connection(self, row_dicts=True):
        '''
        create and cache one connection instance.
        '''
        conn = self._connection

        if conn is None:
            conn = self._connection = \
                   sqlite.connect(self.db_path, **self.connection_args)
            conn.text_factory = self.text_factory

            if self.pragmas:
                cursor = conn.cursor(self.cursor_class)
                for pragma in self.pragmas:
                    cursor.execute('pragma ' + pragma)

        if row_dicts:
            rf = self._dict_factory
        else:
            rf = None
        conn.row_factory = rf

        self._row_dicts = row_dicts  # flag state of current connectoin

        return conn


    def get_cursor(self, row_dicts=True, reuse=True):
        '''
        get hold of a cursor - we reuse by default.
        '''
        if not reuse or row_dicts != self._row_dicts or self._cursor is None:
            self._cursor = self.get_connection(row_dicts).cursor(self.cursor_class)
        return self._cursor


    def execute(self, stmt, values=None, row_dicts=True):
        '''
        shortcut to cursor execute. The idea is to be able to
        use the DB instance directly for everything
        '''
        c = self.get_cursor(row_dicts)

        if values is not None:
            c.execute(stmt, values)
        else:
            c.execute(stmt)

        return c


    def execute_qmarks(self, stmt, value_lists, row_dicts=True):
        '''
        value_lists is a list of lists (or iterable of iterables). Each of
        these must correspond to a single (%s) interpolation marker in stmt,
        which will be substituted with the appropriate number of question marks.
        '''
        vl = list(value_lists)
        frags = stmt.split('(%s)')
        assert len(frags) - 1 == len(vl), 'number of interpolation markers and value lists does not match'

        qmarks, flattened = [], []

        for values in vl:
            v = list(values)
            assert len(v) > 0; "execute_qmarks can't use an empty list of values"
            flattened.extend(v)
            qmarks.append(','.join('?' * len(v)))

        stmt = stmt % tuple(qmarks)

        return self.execute(stmt, flattened, row_dicts)


    def _prepare_insert(self, table, valuedict):
        '''
        shared code for insert and insert_many
        '''
        columns = list(valuedict.keys())  # self.columns(table) - foobars with automatic colums -
                                    # it seems we can't get hold of autoincrement and such
        qmarks = list('?' * len(columns))
        qmarks = ','.join(qmarks)
        stmt = 'insert into %s (%s) values (%s)' % (table, ', '.join(columns), qmarks)

        return columns, stmt


    def insert(self, table, valuedict):
        '''
        we are already going down the poor man's ORM path again
        valuedict maps column names to values to be inserted.
        '''
        columns, stmt = self._prepare_insert(table, valuedict)
        vals = tuple([valuedict[col] for col in columns])

        return self.execute(stmt, vals)


    def insert_many(self, table, valuedicts):
        '''
        test if .executemany can speed things up.
        We assume that all valuedicts are created equal.
        We also guard against the list being empty.

        Well, after testing it on the two longest tables in the mbib database,
        it appears that speed-up is marginal. Not worth any code contortions.
        '''
        if len(valuedicts) == 0:
            return

        columns, stmt = self._prepare_insert(table, valuedicts[0])
        valuetuples = []
        for vd in valuedicts:
            valuetuples.append(tuple([vd[col] for col in columns]))

        return self.executemany(stmt, valuetuples)


    def close(self):
        '''
        close down connection if no longer needed
        '''
        assert self._connection is not None, "no connection has been opened"
        self._connection.close()
        self._connection = None


    def commit(self):
        assert self._connection is not None, "no connection has been opened"
        self._connection.commit()


    def __getattr__(self, att):
        '''
        by default, we can delegate to connection.
        Does this supply .executescript? Apparently so,
        since the call goes through.
        '''
        conn = self.get_connection()
        return getattr(conn, att)





if __name__ == '__main__':

    db = SqliteDB()
    # obviously, we should test some more here
