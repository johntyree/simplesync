#!/usr/bin/env python

from pysqlite2 import dbapi2 as sqlite

#connection = sqlite.connect('/tmp/test.db')
connection = sqlite.connect(':memory:')
cursor = connection.cursor()

cursor.execute('CREATE TABLE names (id INTEGER PRIMARY KEY, name VARCHAR(50), email VARCHAR(50))')
cursor.execute('INSERT INTO names VALUES (null, "John Doe", "jdoe@jdoe.zz")')
cursor.execute('INSERT INTO names VALUES (null, "Mary Sue", "msue@msue.yy")')
connection.commit()
cursor.execute('SELECT * FROM names')

for row in cursor:
    print 'ID:    ', row[0]
    print 'Name:  ', row[1]
    print 'Email: ', row[2]
    
