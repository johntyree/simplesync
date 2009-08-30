#!/usr/bin/env python
from pysqlite2 import dbapi2 as sqlite
import time, sys, os, tagpy, subprocess


class musicDB:
    def __init__ (self, dbfile):
        '''A database of file information and tag attributes'''
        self.connection = sqlite.connect(dbfile)
        self.cursor = self.connection.cursor()
        for table in "file", "album", "artist", "genre":
            self.cursor.execute('DROP TABLE IF EXISTS %s' % table)
        self.cursor.execute('CREATE TABLE file (path VARCHAR(255) PRIMARY KEY, timestamp DECIMAL(12), size INTEGER(12), name VARCHAR(255), artist_id INTEGER, album_id INTEGER, genre_id INTEGER, year INTEGER, copy BOOLEAN)')
        for table in "album", "artist", "genre":
            self.cursor.execute('CREATE TABLE %s (id INTEGER PRIMARY KEY, name VARCHAR(255))' % table)
        self.connection.commit()

    def addDir(self, rootdir):
        '''Recursively import a directory into the database'''
        cursor = self.cursor
        for root, dirs, files in os.walk(rootdir):
            print root
            for name in files:
                if not '.mp3' in name[-4:]:
                    continue
                abspath = os.path.join(root, name)
                relpath = unicode(os.path.relpath(abspath, rootdir), 'latin-1')
                statinfo = os.stat(abspath)
                f = tagpy.FileRef(abspath)
                print f.tag().album
                cursor.execute('SELECT id FROM artist WHERE name = ?', (f.tag().artist,))
                try:
                    artist_id = cursor.fetchall()[0][0]
                except (IndexError):
                    cursor.execute('INSERT INTO artist VALUES (null, ?)', (f.tag().artist,))
                    cursor.execute('SELECT id FROM artist WHERE name = ?', (f.tag().artist,))
                    artist_id = cursor.fetchall()[0][0]
                cursor.execute('SELECT id FROM genre WHERE name = ?', (f.tag().genre,))
                try:
                    genre_id = cursor.fetchall()[0][0]
                except (IndexError):
                    cursor.execute('INSERT INTO genre VALUES (null, ?)', (f.tag().genre,))
                    cursor.execute('SELECT id FROM genre WHERE name = ?', (f.tag().genre,))
                    genre_id = cursor.fetchall()[0][0]
                cursor.execute('SELECT id FROM album WHERE name = ?', (f.tag().album,))
                try:
                    album_id = cursor.fetchall()[0][0]
                except (IndexError):
                    cursor.execute('INSERT INTO album VALUES (null, ?)', (f.tag().album,))
                    cursor.execute('SELECT id FROM album WHERE name = ?', (f.tag().album,))
                    album_id = cursor.fetchall()[0][0]
                cursor.execute('INSERT INTO file VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (relpath, statinfo.st_mtime, statinfo.st_size, f.tag().title, artist_id, album_id, genre_id, f.tag().year, True))
        self.connection.commit()

def main():
    #subprocess.call(["rm","/tmp/test.db"])
    #connection = sqlite.connect('/tmp/test.db')
    db = musicDB(":memory:") 
    rootdir = "/media/disk/Music/S/Sneaky Sound System"
    db.addDir(rootdir)


if __name__ == "__main__": main()




"""shutil.copy2 does metadata, os.stat().st_mtime"""
