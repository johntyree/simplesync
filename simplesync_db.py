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
import os, tagpy, time, bz2, pickle

#Acceptible filetypes for tagpy
filetypes = ('mp3', 'ogg')

class musicDB:
    '''A database of file information and tag attributes.'''

    def __init__ (self, dbfile):
        '''Initialize a musicDB object connected to <dbfile>.'''
        self.echo = True
        self.dbfile = dbfile
        isNew = False
        if self.echo: print "Connecting to %s" % dbfile
        if not os.path.isfile(dbfile):
            isNew = True
            try:
                if self.echo: print "New DB: ", dbfile
                if dbfile != ":memory:": os.makedirs(os.path.dirname(dbfile))
            except OSError, e:
                if not os.path.isdir(os.path.dirname(dbfile)):
                    print "Failed to create DB: %s" % e.strerror
        self.connection = sqlite.connect(dbfile)
        self.cursor = self.connection.cursor()
        if isNew:
            self.rebuild()
        if self.echo: print "Connected"

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
        if self.echo: print "Rebuilding...",
        target = self.targetDir()
        source = self.sourceDir()

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
        self.targetDir(target)
        self.sourceDir(source)
        self.connection.commit()
        if self.echo: print 'complete!'

    def removeFile(self, sourceDir, abspath):
        '''Remove a file from the database.'''
        relpath = os.path.relpath(abspath, sourceDir)
        if self.echo: print "db.removeFile: ", relpath
        try:
            relpath = unicode(relpath, 'utf-8')
        except TypeError:
            pass
        self.cursor.execute('DELETE FROM file WHERE relpath = ?', (relpath,))

    def updateFile(self, sourceDir, abspath):
        '''Update a file in the database.'''
        relpath = os.path.relpath(abspath, sourceDir)
        if self.echo: print "db.updateFile: ", relpath
        self.cursor.execute('SELECT sync FROM file where relpath = ?', (relpath,))
        sync = 0
        try:
            sync = self.cursor.fetchall()[0][0]
        except IndexError:
            pass
        self.removeFile(sourceDir, abspath)
        self.addFile(sourceDir, abspath)
        if (sync): self.setSync([(relpath, sync)])

    def addFile(self, sourceDir, abspath):
        '''Add a file and its tag information to the database.'''
        statinfo = os.stat(abspath)
        #if not '.mp3' in abspath[-4:] or '.ogg' in abspath[-4:]
        print abspath
        try:
            f = tagpy.FileRef(abspath.encode('utf-8')) # Because tagpy apparently can't process unicode
        except ValueError, e:
            print "ValueError:", e.message, abspath
            return False
        #relpath  unicode(os.path.relpath(abspath, sourceDir), 'utf-8')
        relpath = os.path.relpath(abspath, sourceDir)
        if self.echo: print "addFile:", (relpath, len(relpath))
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
        return True

    def copySize(self):
        '''Return the size, in bytes, of all files marked for copy at the next sync.'''
        self.cursor.execute('SELECT relpath, size FROM file WHERE sync = ?', (True,))
        results = self.cursor.fetchall()
        total = 0
        copyList = self.copyList()
        for relpath, size in results:
            if relpath in copyList:
                total += size
        return total

    def syncSize(self):
        '''Return the size, in bytes, of all files marked for sync.'''
        self.cursor.execute('SELECT relpath, size FROM file WHERE sync = ?', (True,))
        results = self.cursor.fetchall()
        total = 0
        for relpath, size in results:
            total += size
        return total

    def fileList(self, sourceDir):
        '''Return a list of all mp3 files below sourceDir.'''
        list = []
        print "fileList->sourceDir:", sourceDir
        try:
            for root, dirs, files in os.walk(sourceDir.decode('utf-8')): # Now a unicode object
            #root = root.encode('latin-1').decode('utf-8')
                if self.echo: print (root,)
                for name in (x for x in files):
                    if not name.rsplit('.', 1)[1] in filetypes:
                        continue
                #print (name,)
                    abspath = os.path.join(root, name)
                #print "fileList:", (abspath,)
                    list.append(abspath)
        except UnicodeDecodeError, e:
            print e.args
            raise UnicodeDecodeError
        return list

    def importDir(self, sourceDir, CONFIG_DIR = None):
        '''Recursively import sourceDir into db. Sync values will persist if
        CONFIG_DIR is specified,'''
        file = ''
        s = time.time()
        if CONFIG_DIR is not None:
            filename = os.path.join(CONFIG_DIR, self.dbfile + '.IMPORT.' + str(int(time.time())))
            self.cursor.execute("SELECT relpath, sync FROM file")
            data = self.cursor.fetchall()
            self.dumpFlatFile(filename, data)
        #self.rebuild()
        for abspath in self.fileList(sourceDir):
            if self.isNewer(sourceDir, sourceDir, os.path.relpath(abspath, sourceDir)):
                self.updateFile(sourceDir, abspath)
        self.connection.commit()
        if CONFIG_DIR is not None:
            self.cleanDB(sourceDir, CONFIG_DIR)
            self.loadSyncFlatFile(filename)
            os.unlink(filename)
        f = time.time()
        print "%.1fs" % (f - s)
        return (f - s)

    def cleanDB(self, sourceDir, CONFIG_DIR):
        '''Remove files from db which do not exist in sourceDir.'''
        trackSet = set(self.trackList())
        fileSet = set([os.path.relpath(x, sourceDir) for x in self.fileList(sourceDir)])
        for track in trackSet - fileSet:
            self.removeFile(sourceDir, os.path.join(sourceDir, track))
        self.connection.commit()
        print "cleanDB:"
        print trackSet
        print fileSet
        print trackSet - fileSet
        print "END cleanDB"
        self.dumpFlatFile(os.path.join(CONFIG_DIR, self.dbfile + '.REMOVED_FROM_DB.' + str(time.time()) + '.bz2'), trackSet - fileSet, False)
        return

    def unknownList(self, sourceDir):
        '''Return a list of files in sourceDir but not in db.'''
        # Get list of all relpaths
        trackList = self.trackList()
        unknownList = []
        for abspath in self.fileList(sourceDir):
            relpath = os.path.relpath(abspath, sourceDir)
            if relpath not in trackList:
                unknownList.append(relpath)
        return unknownList

    def extraList(self, targetDir):
        '''Return a list of files in targetDir but not in db OR not marked for sync.'''
        extra = self.unknownList(targetDir)
        self.cursor.execute('SELECT relpath FROM file WHERE sync = ?', (False,))
        try:
            noSyncs = (x[0] for x in self.cursor.fetchall())
        except IndexError:
            noSyncs = []
        for relpath in noSyncs:
            if os.path.exists(os.path.join(targetDir, relpath)):
                extra.append(relpath)
        return extra

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

    def isNewer(self, sourceDir, targetDir, relpath):
        '''Return True if file at sourceDir/relpath is newer than or not present in the database.targetDir/relpath does not exist.'''
        if not os.path.exists(os.path.join(targetDir, relpath)):
            return True
        self.cursor.execute('SELECT mtime FROM file WHERE relpath = ?', (relpath,))
        try:
            dbTime = self.cursor.fetchall()[0][0]
            fileTime = os.stat(os.path.join(sourceDir, relpath)).st_mtime
            return fileTime > dbTime
        except IndexError:
            print "File not in DB (True): %s" % relpath
            return True
        except OSError:
            print "File in DB but not sourceDir (False): %s" % relpath
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

    def copyList(self, sourceDir = None, targetDir = None):
        '''Returns a list of files to be transfered at next sync.'''
        if not sourceDir: sourceDir = self.sourceDir()
        if not targetDir: targetDir = self.targetDir()
        copyList = []
        for relpath in self.syncList():
            #print (relpath,),
            if not '.mp3' in relpath[-4:].lower():
                continue
            if self.isNewer(sourceDir, targetDir, relpath):
                #print "NEWER"
                copyList.append(relpath)
            #else: print
        return copyList

    def trackList(self):
        '''Return a list of relative paths of all files in db.'''
        self.cursor.execute('SELECT relpath FROM file')
        tupleList = self.cursor.fetchall()
        trackList = [x[0] for x in tupleList]
        return trackList

    def syncList(self):
        '''Return a list of relative paths of all files marked for sync.'''
        self.cursor.execute('SELECT relpath FROM file WHERE sync = 1')
        tupleList = self.cursor.fetchall()
        syncList = [x[0] for x in tupleList]
        #if self.echo: print syncList
        return syncList

    def setSync(self, relpathList):
        '''Sets the sync value of each of a tuple of a tuple of files in the db.
        Each inner tuple contains the file's relpath and desired sync value.'''
        for relpath, sync in relpathList:
            #relpath = unicode(relpath, 'utf-8')
            sync = bool(sync)
            self.cursor.execute("UPDATE file SET sync = ? WHERE relpath = ?", (sync, relpath))
            if self.echo:
                self.cursor.execute("SELECT sync FROM file where relpath = ?", (relpath,))
                try:
                    if self.cursor.fetchall()[0][0] == sync:
                        print "OK",
                    else:
                        print "Failed!",
                except IndexError:
                    print "File not found in DB.",
                print "setSync: %-5s - %s" % (sync, relpath.encode('utf-8'))
        self.connection.commit()
        return

    def dumpFlatFile(self, outfile, data, pickleIt = True):
        '''Write bz2 compressed, optionally pickled data to outfile.
        If pickleIt is False, data must be an iterable representing file lines.'''
        out = bz2.BZ2File(outfile, "w")
        if pickleIt:
            pickle.dump(data, out, 2)
        else:
            for line in data:
                print >> out, line
        out.close()
        return

    def readFlatFile(self, infile):
        '''Return bz2 decompressed, unpickled data from infile.'''
        inf = bz2.BZ2File(infile, 'rb')
        data = pickle.load(inf)
        inf.close()
        return data

    def loadSyncFlatFile(self, infile):
        '''Read relpaths from database dump at infile.
        Write files which are missing from DB to -EXTRA_IN_SYNCLIST.bz2.
        Write files which are in DB but not in file to -NEW_IN_DB.bz2.'''
        tracks = self.trackList()
        syncUpdates = []
        data = self.readFlatFile(infile)
        for relpath, sync in data:
            if relpath in tracks:
                syncUpdates.append((relpath, sync))
            else:
                if self.echo: print relpath, "not found!"
        self.setSync(syncUpdates)
        filelist = sorted(list(set((x[0] for x in syncUpdates)) - set(tracks)))
        if bool(filelist):
            self.dumpFlatFile(infile + "-EXTRA_IN_SYNCLIST.bz2", filelist, False)
        filelist = sorted(list(set(tracks) - set((x[0] for x in syncUpdates))))
        if bool(filelist):
            self.dumpFlatFile(infile + "-NEW_IN_DB.bz2", filelist, False)
        return syncUpdates


def main():
    db = musicDB(":memory:")
    sourceDir = "/media/disk/Music/A/Abd Al Malik"
    db.rebuild()
    db.importDir(sourceDir)
    #db.dumpFlatFile("/tmp/dbdump")
    #db.loadSyncFlatFile("/home/john/.simplesync/ipodDump")

if __name__ == "__main__": main()
