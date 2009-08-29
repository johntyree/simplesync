#!/usr/bin/env python

from pysqlite2 import dbapi2 as sqlite
import time, sys, os

connection = sqlite.connect('/tmp/test.db')
cursor = connection.cursor()
try:
    cursor.execute('CREATE TABLE files (id INTEGER PRIMARY KEY, path VARCHAR(255), timestamp DECIMAL(12), size INTEGER(12))')
except (sqlite.OperationalError):
    pass
connection.commit()

rootdir = "/media/disk/Music/0-9"
for root, dirs, files in os.walk(rootdir):
    for name in files:
        abspath = os.path.join(root, name)
        relpath = os.path.relpath(abspath, rootdir)
        statinfo = os.stat(abspath)
        cursor.execute('INSERT INTO files VALUES (null, ?, ?, ?)', (relpath, statinfo.st_mtime, statinfo.st_size))
        connection.commit()
        #print name + ":",  statinfo.st_mtime, statinfo.st_size
"""os.path.commonprefix(list), shutil.copy2 does metadata, os.stat().st_mtime"""
sys.exit()








for row in cursor:
    try:
        print 'ID: ', row[0], 'Parent: ', row[1], 'path: ', row[3]
    except (UnicodeEncodeError):
        print 'Fucked up Unicode or something ****'
    
