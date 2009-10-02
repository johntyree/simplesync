#!/usr/bin/env python
#
#       db.py
#       
#       Copyright 2009 John Tyree <johntyree@gmail.com>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 3 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.


from pysqlite2 import dbapi2 as sqlite
import os, tagpy, time


class musicDB:
    '''A database of file information and tag attributes.'''

    def __init__ (self, dbfile):
        '''Initialize a musicDB object connected to <dbfile>.'''
        self.dbfile = dbfile
        self.connection = sqlite.connect(dbfile)
        self.cursor = self.connection.cursor() 

    def mtime(self, time = -1):
        '''Return or set the time, in seconds, that the db was last modified.'''
        if (time != -1):
            self.cursor.execute('SELECT value FROM metadata WHERE name = mtime')
            return self.cursor.fetchall()[0][0]
        self.cursor.execute('UPDATE metadata SET value = ? WHERE name = mtime', (time,))
        self.connection.commit()
        return True

    def rebuild(self):
        '''Create a new empty database.'''
        for table in "file", "album", "artist", "genre", "metadata":
            self.cursor.execute('DROP TABLE IF EXISTS %s' % (table,))
        self.cursor.execute('CREATE TABLE file (relpath VARCHAR(255) PRIMARY KEY, mtime DECIMAL(12), size INTEGER(12), title VARCHAR(255), artist_id INTEGER, album_id INTEGER, genre_id INTEGER, year INTEGER, sync BOOLEAN)')
        for table in "album", "artist", "genre":
            self.cursor.execute('CREATE TABLE %s (id INTEGER PRIMARY KEY, name VARCHAR(255))' % (table,))
        self.cursor.execute('CREATE TABLE metadata (name VARCHAR(255) PRIMARY KEY, value VARCHAR(255))')
        self.cursor.execute('INSERT INTO metadata VALUES (?, ?)', ("db_version", 0.0))
        self.cursor.execute('INSERT INTO metadata VALUES (?, ?)', ("simplesync_version", 0.0))
        self.connection.commit()
        self.mtime(time.localtime())

    def removeFile(self, rootdir, abspath):
        '''Remove a file from the database.'''
        relpath = unicode(os.path.relpath(abspath, rootdir), 'latin-1')
        self.cursor.execute('DELETE FROM file WHERE relpath = ?', (relpath,)) 
        self.mtime(time.localtime())

    def updateFile(self, rootdir, abspath):
        '''Update a file in the database'''
        self.removeFile(rootdir, abspath)
        self.addFile(rootdir, abspath)
        self.mtime(time.localtime())

    def addFile(self, rootdir, abspath):
        '''Add a file and its tag information to the database.'''
        statinfo = os.stat(abspath)
        f = tagpy.FileRef(abspath)
        relpath = unicode(os.path.relpath(abspath, rootdir), 'latin-1')
        # One for each field...
        self.cursor.execute('SELECT id FROM artist WHERE name = ?', (f.tag().artist,))
        temp = self.cursor.fetchall()
        if temp == []:
            self.cursor.execute('INSERT INTO artist VALUES (null, ?)', (f.tag().artist,))
            self.cursor.execute('SELECT id FROM artist WHERE name = ?', (f.tag().artist,))
            temp = self.cursor.fetchall()
        artist_id = temp[0][0]
        self.cursor.execute('SELECT id FROM genre WHERE name = ?', (f.tag().genre,))
        temp = self.cursor.fetchall()
        if temp == []:
            self.cursor.execute('INSERT INTO genre VALUES (null, ?)', (f.tag().genre,))
            self.cursor.execute('SELECT id FROM genre WHERE name = ?', (f.tag().genre,))
            temp = self.cursor.fetchall()
        genre_id = temp[0][0]
        self.cursor.execute('SELECT id FROM album WHERE name = ?', (f.tag().album,))
        temp = self.cursor.fetchall()
        if temp == []:
            self.cursor.execute('INSERT INTO album VALUES (null, ?)', (f.tag().album,))
            self.cursor.execute('SELECT id FROM album WHERE name = ?', (f.tag().album,))
            temp = self.cursor.fetchall()
        album_id = temp[0][0]
        self.cursor.execute('INSERT INTO file VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (relpath, statinfo.st_mtime, statinfo.st_size, f.tag().title, artist_id, album_id, genre_id, f.tag().year, True))
        self.connection.commit()
        self.mtime(time.localtime())

    def recurseDir(self, rootDir, func = updateFile):
        '''Recursively call func() on a relative path.'''
        for root, dirs, files in os.walk(rootDir):
            print root
            for name in files:
                if not '.mp3' in name[-4:]:
                    continue
                abspath = os.path.join(root, name)
                func(rootDir, abspath)
                #self.updateFile(rootDir, abspath)

    def isNewer(self, rootdir, relpath):
        '''Return True if file has been modified.'''
        self.cursor.execute('SELECT mtime FROM file WHERE relpath = ?', (relpath,))
        try:
            dbTime = self.cursor.fetchall()[0][0]
            fileTime = os.stat(os.path.join(rootdir, relpath)).st_mtime
            return fileTime > dbTime
        except (IndexError):
            return True

    def filterList(self, str):
        '''Return list of tuples of metadata from the db which match str.'''
        list = filter(lambda x: str in x, self.allList())
        return list

    def allList(self):
        '''Return a list of dictionaries of metadata from each track.'''
        self.cursor.execute('SELECT * FROM file')
        rows = self.cursor.fetchall()
        allList = []
        for (relpath, mtime, size, title, artist_id, album_id, genre_id, year, sync) in rows:
            self.cursor.execute('SELECT name FROM genre where id = ?', (genre_id,))
            genre = self.cursor.fetchall()[0][0]
            self.cursor.execute('SELECT name FROM artist where id = ?', (artist_id,))
            artist = self.cursor.fetchall()[0][0]
            self.cursor.execute('SELECT name FROM album where id = ?', (album_id,))
            album = self.cursor.fetchall()[0][0]
            allList.append({"relpath" : relpath, "mtime" : mtime, "size" : size, "title" : title, "artist" : artist, "album" : album, "genre" : genre, "year" : year, "sync" : sync}) 
        return allList

    def copyList(self, rootDir):
        '''Returns a list of files to be transfered at next sync.'''
        print 'copyList()... '
        copyList = []
        #for root, dirs, files in os.walk(rootDir):
        for relpath in self.syncList():
            #for name in files:
                if not '.mp3' in relpath[-4:].lower():
                    print relpath
                    continue
                if self.isNewer(rootDir, relpath):
                    copyList.append(relpath)
        print 'end'
        return copyList

    def trackList(self):
        '''Return a list of relative paths of all files in db.'''
        self.cursor.execute('SELECT relpath FROM file')
        tupleList = self.cursor.fetchall()
        trackList = []
        for t in tupleList:
            trackList.append(t[0])
        return trackList

    def syncList(self):
        '''Return a list of relative paths of all files marked for sync.'''
        self.cursor.execute('SELECT relpath FROM file WHERE sync = 1')
        tupleList = self.cursor.fetchall()
        syncList = []
        for t in tupleList:
            syncList.append(t[0])
        return syncList

    def setSync(self, relpathList):
        '''Sets the sync value of each of a tuple of files in the db.
        The tuple should contain the file's relpath and desired sync value.'''
        for relpath, sync in relpathList: 
            relpath = unicode(relpath, 'latin-1')
            print relpath
            #print "Toggled %s to %s" % (relpath, sync)
            self.cursor.execute("UPDATE file SET sync = ? WHERE relpath = ?", (sync, relpath))
        self.connection.commit()
        return

def main():
    #subprocess.call(["rm","/tmp/test.db"])
    #connection = sqlite.connect('/tmp/test.db')
    db = musicDB(":memory:") 
    rootdir = "/media/disk/Music/S/Sneaky Sound System"
    db.addDir(rootdir)
    print db.syncList()


if __name__ == "__main__": main()




"""shutil.copy2 does metadata, os.stat().st_mtime"""
