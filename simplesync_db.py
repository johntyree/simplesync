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
        print "Connecting to %s" % dbfile
        self.dbfile = dbfile
        isNew = False
        if not os.path.isfile(dbfile):
            isNew = True
            try:
                print "New DB: ", dbfile
                os.makedirs(os.path.dirname(dbfile))
            except OSError, e:
                if not os.path.isdir(os.path.dirname(dbfile)):
                    print "Failed to create DB: %s" % e.strerror
        self.connection = sqlite.connect(dbfile)
        self.cursor = self.connection.cursor()
        if isNew:
            self.rebuild()
        print "Connected"

    def mtime(self, time = None):
        '''Return or set the time, in seconds, of the start of the previous sync.'''
        if (time == None):
            self.cursor.execute('SELECT value FROM metadata WHERE name = mtime')
            return self.cursor.fetch()[0]
        self.cursor.execute('INSERT OR REPLACE INTO metadata VALUES (?, ?)', ('mtime', time))
        self.connection.commit()
        return True

    def rebuild(self):
        '''Construct a new empty database.'''
        print "Rebuilding...",

        # Drop all tables ...
        self.cursor.execute('''SELECT 'DROP TABLE ' || name || ';'
                            FROM sqlite_master where type = 'table';''')
        drops = self.cursor.fetchall()
        for query in drops:
            self.cursor.execute(query[0])
        self.connection.commit()

        # Start rebuilding
        self.cursor.execute('''
             CREATE TABLE file (
                relpath VARCHAR(255) PRIMARY KEY,
                mtime DECIMAL(12) NOT NULL,
                size INTEGER(12) NOT NULL,
                title VARCHAR(255),
                artist_id INTEGER,
                album_id INTEGER,
                genre_id INTEGER,
                year INTEGER,
                sync BOOLEAN NOT NULL)
        ''')
        for table in "album", "artist", "genre":
            self.cursor.execute('CREATE TABLE %s (id INTEGER PRIMARY KEY, name VARCHAR(255))' % (table,))
        self.cursor.execute('CREATE TABLE metadata (name VARCHAR(255) PRIMARY KEY, value VARCHAR(255))')
        self.cursor.execute('INSERT INTO metadata VALUES (?, ?)', ("db_version", 0.0))
        self.cursor.execute('INSERT INTO metadata VALUES (?, ?)', ("simplesync_version", 0.0))
        self.connection.commit()
        print 'complete!'

    def removeFile(self, sourceDir, abspath):
        '''Remove a file from the database.'''
        relpath = os.path.relpath(abspath, sourceDir)
        print "db.removeFile: ", relpath
        try:
            relpath = unicode(relpath, 'latin-1')
        except TypeError:
            pass
        self.cursor.execute('DELETE FROM file WHERE relpath = ?', (relpath,))

    def updateFile(self, sourceDir, abspath):
        '''Update a file in the database.'''
        print "db.updateFile: ", unicode(os.path.relpath(abspath, sourceDir), 'latin-1')
        self.removeFile(sourceDir, abspath)
        self.addFile(sourceDir, abspath)

    def addFile(self, sourceDir, abspath):
        '''Add a file and its tag information to the database.'''
        statinfo = os.stat(abspath)
        f = tagpy.FileRef(abspath)
        relpath = unicode(os.path.relpath(abspath, sourceDir), 'latin-1')
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

    def syncSize(self):
        '''Return the size, in bytes, of all files marked for sync.'''
        self.cursor.execute('SELECT relpath, size FROM file WHERE sync = ?', (True,))
        results = self.cursor.fetchall()
        total = 0
        for relpath, size in results:
            total += size
        return total

    def recurseDir(self, sourceDir, func = updateFile):
        '''Recursively call func() on a relative path.'''
        s = time.time()
        for root, dirs, files in os.walk(sourceDir):
            print root
            for name in files:
                if not '.mp3' in name[-4:]:
                    continue
                abspath = os.path.join(root, name)
                func(sourceDir, abspath)
        self.connection.commit()
        self.sourceDir(sourceDir)
        return True

    def targetDir(self, dir = None):
       if dir:
           self.cursor.execute('INSERT OR REPLACE INTO metadata VALUES (?, ?)', ('targetDir', dir))
           self.connection.commit()
       else:
           self.cursor.execute('SELECT value FROM metadata WHERE name = ?', ('targetDir',))
           dir = self.cursor.fetchone()
           if dir != None:
               return dir[0]

    def sourceDir(self, dir = None):
       if dir:
           self.cursor.execute('INSERT OR REPLACE INTO metadata VALUES (?, ?)', ('sourceDir', dir))
           self.connection.commit()
       else:
           self.cursor.execute('SELECT value FROM metadata WHERE name = ?', ('sourceDir',))
           dir = self.cursor.fetchone()
           if dir != None:
               return dir[0]

    def isNewer(self, sourceDir, relpath):
        '''Return True if file at sourceDir/relpath is newer or is not in database.'''
        self.cursor.execute('SELECT mtime FROM file WHERE relpath = ?', (relpath,))
        try:
            dbTime = self.cursor.fetchall()[0][0]
            fileTime = os.stat(os.path.join(sourceDir, relpath)).st_mtime
            return fileTime > dbTime
        except IndexError:
            return True
        except OSError:
            return False

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

    def copyList(self, sourceDir):
        '''Returns a list of files to be transfered at next sync.'''
        copyList = []
        #for root, dirs, files in os.walk(sourceDir):
        for relpath in self.syncList():
            #for name in files:
                if not '.mp3' in relpath[-4:].lower():
                    continue
                if self.isNewer(sourceDir, relpath):
                    copyList.append(relpath)
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
        '''Sets the sync value of each of a tuple of a tuple of files in the db.
        The each inner tupple contains the file's relpath and desired sync value.'''
        for relpath, sync in relpathList:
            relpath = unicode(relpath, 'latin-1')
            print "setSync: %-5s - %s" % (sync, relpath)
            self.cursor.execute("UPDATE file SET sync = ? WHERE relpath = ?", (sync, relpath))
        self.connection.commit()
        return

def main():
    db = musicDB(":memory:")
    sourceDir = "/media/disk/Music/S"
    db.rebuild()
    db.recurseDir(sourceDir, db.addFile)

if __name__ == "__main__": main()
