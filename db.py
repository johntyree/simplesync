#!/usr/bin/env python
from pysqlite2 import dbapi2 as sqlite
import time, sys, os, tagpy, subprocess


class musicDB:
    def __init__ (self, dbfile):
        '''A database of file information and tag attributes'''
        self.connection = sqlite.connect(dbfile)
        self.cursor = self.connection.cursor()
        for table in "file", "album", "artist", "genre":
            self.cursor.execute('DROP TABLE IF EXISTS %s' % (table,))
        self.cursor.execute('CREATE TABLE file (relpath VARCHAR(255) PRIMARY KEY, mtime DECIMAL(12), size INTEGER(12), title VARCHAR(255), artist_id INTEGER, album_id INTEGER, genre_id INTEGER, year INTEGER, sync BOOLEAN)')
        for table in "album", "artist", "genre":
            self.cursor.execute('CREATE TABLE %s (id INTEGER PRIMARY KEY, name VARCHAR(255))' % (table,))
        self.cursor.execute('CREATE TABLE metadata (name VARCHAR(255) PRIMARY KEY, value VARCHAR(255))')
        self.cursor.execute('INSERT INTO metadata VALUES (?, ?)', ("db_version", 0.0))
        self.cursor.execute('INSERT INTO metadata VALUES (?, ?)', ("simplesync_version", 0.0))
        self.connection.commit()

    def addDir(self, rootdir):
        '''Recursively import a directory into the database'''
        for root, dirs, files in os.walk(rootdir):
            print root
            for name in files:
                if not '.mp3' in name[-4:]:
                    continue
                abspath = os.path.join(root, name)
                self.updateFile(rootdir, abspath)

    def removeFile(self, rootdir, abspath):
        relpath = unicode(os.path.relpath(abspath, rootdir), 'latin-1')
        self.cursor.execute('DELETE FROM file WHERE relpath = ?', (relpath,)) 

    def updateFile(self, rootdir, abspath):
        self.removeFile(rootdir, abspath)
        self.addFile(rootdir, abspath)

    def addFile(self, rootdir, abspath):
        statinfo = os.stat(abspath)
        f = tagpy.FileRef(abspath)
        cursor = self.cursor
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
        relpath = unicode(os.path.relpath(abspath, rootdir), 'latin-1')
        cursor.execute('INSERT INTO file VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (relpath, statinfo.st_mtime, statinfo.st_size, f.tag().title, artist_id, album_id, genre_id, f.tag().year, True))
        self.connection.commit()


    def isNewer(self, rootdir, relpath):
        self.cursor.execute('SELECT mtime FROM file WHERE relpath = ?', (relpath,))
        dbTime = self.cursor.fetchall()[0][0]
        fileTime = os.stat(os.path.join(rootdir, relpath)).st_mtime
        return fileTime > dbTime

    def syncList(self):
        self.cursor.execute('SELECT relpath FROM file WHERE sync = 1')
        tupleList = self.cursor.fetchall()
        syncList = []
        for t in tupleList:
            syncList.append(t[0])
        return syncList

def main():
    #subprocess.call(["rm","/tmp/test.db"])
    #connection = sqlite.connect('/tmp/test.db')
    db = musicDB(":memory:") 
    rootdir = "/media/disk/Music/S/Sneaky Sound System"
    db.addDir(rootdir)
    print db.syncList()


if __name__ == "__main__": main()




"""shutil.copy2 does metadata, os.stat().st_mtime"""
