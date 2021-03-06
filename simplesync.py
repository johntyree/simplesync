#!/usr/bin/env python
#
#       simplesync.py
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

import gtk, gobject, time, os, shutil, sys, statvfs, subprocess, threading
import simplesync_db

CONFIG_DIR = os.path.expanduser("~/.simplesync/")
def currentTime():
    return ''.join(["%02u" % x for x in time.localtime()[:-3]])

class dbView:
    '''Main window for viewing simplesync musicDB'''

    def __init__(self, dbFile = None):
        self.echo = False
        self.appPath = os.path.abspath(os.path.dirname(os.path.realpath(sys.argv[0])))
        self.dbFile = dbFile

        # Initialize model
        self.allToggle = None
        self.filtered = None

        ## Generate tooltips
        self.tooltips = gtk.Tooltips()

        ## Keyboard Accelerators
        self.AccelGroup = gtk.AccelGroup()
        self.AccelGroup.connect_group(ord('O'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED, lambda w, x, y, z: self.editPrefs())
        self.AccelGroup.connect_group(ord('P'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED, lambda w, x, y, z: self.playTrackFromColumn())
        self.AccelGroup.connect_group(ord('Q'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED, lambda w, x, y, z: gtk.main_quit())
        self.AccelGroup.connect_group(ord('S'), gtk.gdk.CONTROL_MASK, gtk.ACCEL_LOCKED, lambda w, x, y, z: self.toggleSelectedButton_callback(x))

        # Track view
        self.tree = gtk.TreeView()
        self.titleCol = gtk.TreeViewColumn("Title")
        self.artistCol = gtk.TreeViewColumn("Artist")
        self.albumCol = gtk.TreeViewColumn("Album")
        self.yearCol = gtk.TreeViewColumn("Year")
        self.genreCol = gtk.TreeViewColumn("Genre")
        self.syncCol = gtk.TreeViewColumn("Sync")
        col_cell_text = gtk.CellRendererText()
        for i, col in enumerate((self.titleCol, self.artistCol, self.albumCol, self.genreCol, self.yearCol)):
            col.pack_start(col_cell_text, True)
            col.add_attribute(col_cell_text, "text", i+1)
            col.set_resizable(True)
            col.set_clickable(True)
            col.set_reorderable(True)
            col.connect("clicked", self.rearrange, i+1)
            #col.set_sort_column_id(i+1)
            #col.set_property('max_width', 300)
            col.set_max_width(200)
            col.set_min_width(25)
            col.set_expand(False)
            #            col.connect('clicked', lambda w: self.column_callback(w))
            self.tree.append_column(col)
        self.titleCol.set_expand(True)
        self.titleCol.set_max_width(-1)
        col_cell_toggle = gtk.CellRendererToggle()
        self.syncCol.pack_start(col_cell_toggle)
        self.syncCol.set_clickable(True)
        self.syncCol.set_max_width(37)
        self.syncCol.connect("clicked", self.rearrange, i+1)
        self.syncCol.add_attribute(col_cell_toggle, "active", 6)
        col_cell_toggle.set_property('activatable', True)
        col_cell_toggle.connect('toggled', self.toggle_callback)
        self.tree.append_column(self.syncCol)
        self.tree.set_rules_hint(True)
        self.tree.connect("row-activated", self.row_callback)
        self.tree.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        # Track window
        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)

        # Search bar
        self.searchBar = gtk.Entry()
        self.searchBar.connect('activate', self.searchBar_callback)
        self.searchBar.set_activates_default(True)
        self.tooltips.set_tip(self.searchBar, "Enter query.")

        # Toggle Selected button
        self.toggleSelectedButton = gtk.Button()
        self.toggleSelectedButton.set_label("_Toggle")
        self.toggleSelectedButton.connect('clicked', self.toggleSelectedButton_callback)
        self.tooltips.set_tip(self.toggleSelectedButton, "Toggle sync of all files.")

        # Delete Selected button
        self.deleteSelectedButton = gtk.Button()
        self.deleteSelectedButton.set_label("_Delete")
        self.deleteSelectedButton.connect('clicked', self.deleteSelectedButton_callback)
        self.tooltips.set_tip(self.deleteSelectedButton, "Delete all selected files.")

        # updateDB button
        self.updateDBButton = gtk.Button('_Update DB')
        self.updateDBButton.set_image(gtk.image_new_from_stock(gtk.STOCK_REFRESH, gtk.ICON_SIZE_BUTTON))
        self.updateDBButton.connect('clicked', self.updateDBButton_callback)
        self.tooltips.set_tip(self.updateDBButton, "Update the database from disk.")

        # Sync button
        self.syncAllButton = gtk.Button('_Sync')
        self.syncAllButton.set_image(gtk.image_new_from_stock(gtk.STOCK_SAVE, gtk.ICON_SIZE_BUTTON))
        self.syncAllButton.connect('clicked', self.syncAllButton_callback)
        self.tooltips.set_tip(self.syncAllButton, "Sync active files to device.")

        # Window layout
        self.vbox1 = gtk.VBox(False, 0)
        self.hbox1 = gtk.HBox(False, 0)
        self.vbox1.pack_start(self.scroll, True, True, 1)
        self.hbox1.pack_start(self.searchBar, True, True, 1)
        self.hbox1.pack_start(self.deleteSelectedButton, False, False, 1)
        self.hbox1.pack_start(self.toggleSelectedButton, False, False, 1)
        self.hbox1.pack_start(self.updateDBButton, False, False, 1)
        self.hbox1.pack_start(self.syncAllButton, False, False, 1)
        self.vbox1.pack_start(self.hbox1, False, False, 1)

        # Initialize
        self.dbwindow = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.dbwindow.set_title("SimpleSync")
        self.dbwindow.set_icon_from_file(os.path.join(self.appPath, 'simplesync.png'))
        self.dbwindow.set_default_size(1000, 400)
        self.dbwindow.connect("destroy", lambda w: gtk.main_quit())
        self.dbwindow.add_accel_group(self.AccelGroup)
        self.dbwindow.add(self.vbox1)
        self.searchBar.grab_focus()
        self.dbwindow.show_all()

        # Populate
        try:
            self.view(self.dbFile)
        except NameError:
            pass

    def rearrange(self, col, n):
        if col.get_sort_order() == gtk.SORT_ASCENDING:
            col.set_sort_order(gtk.SORT_DESCENDING)
        else:
            col.set_sort_order(gtk.SORT_ASCENDING)
        self.listStore.set_sort_column_id(n, col.get_sort_order())
        col.set_sort_indicator(True)

    def view(self, dbFile):
        '''Load the database into the dbView.'''
        # We have to make a filter here and use get_model to ref the backend so
        # we can search later on
        if dbFile == None:
            print "No file specified!"
            return
        db = self.openDB(dbFile)
        self.db = db
        self.dbwindow.set_title('SimpleSync - %s: [ %s -> %s ]' % (dbFile, db.sourceDir(), db.targetDir()))
        self.listStore = gtk.ListStore(str, str, str, str, str, int, bool)
        for track in db.allList():
            self.listStore.append([track['relpath'], track['title'], track['artist'], track['album'], track['genre'], track['year'], track['sync']])
        self.filterModel = self.listStore.filter_new()
        self.filterModel.set_visible_func(self.filterFunc, self.searchBar)
        self.tree.set_model(self.filterModel)
        self.tree.columns_autosize()
        self.updateTitle()

    def updateTitle(self):
        '''Update window title.'''
        syncSize = self.db.fileListSize(self.visibleSyncFiles()) / 1024.**2
        targetSize = totalSpace(self.db.targetDir()) / 1024.**2
        unit = 'Mib'
        title = None
        if syncSize > 1024 or targetSize > 1024:
            syncSize /= 1024.0
            targetSize /= 1024.0
            unit = 'Gib'
        try:
            percent = (syncSize / targetSize) * 100.0
        except ZeroDivisionError:
            percent = 0
        if len(self.filterModel):
            title = ('SimpleSync - %s: [ %s -> %s ] (%i/%i) (%.2f / %.2f %s %2i%%)' % (self.dbFile, self.db.sourceDir(), self.db.targetDir(), len(self.filterModel), len(self.listStore), syncSize, targetSize, unit, percent))
        else:
            title = ('SimpleSync - %s: [ %s -> %s ] (%i) (%.2f / %.2f %s %i%%)' % (self.dbFile, self.db.sourceDir(), self.db.targetDir(), len(self.filterModel), syncSize, targetSize, unit, percent))
        try:
            title = ('(%.1fs) %s' % (self.opTime, title))
        except AttributeError:
            pass
        if self.echo: print title, type(title)
        self.dbwindow.set_title(title)

    def searchBar_callback(self, searchBar):
        '''Limit results to those containing 'searchBar'.'''
        # To avoid constant refiltering
        self.filterModel.refilter()
        self.updateTitle()

    def filterFunc(self, model, row, searchBar):
        '''Return True if searchBarText matches any part of any column in row.'''
        if self.filtered: return True
        searchBarText = searchBar.get_text().lower()
        for text in model.get(row, 1, 2, 3, 4,):
            if searchBarText in text.lower(): return True

    def toggle_callback(self, cell, toggleList):
        '''Toggle sync status of a tuple of files in db.'''
        # Ugly workaround based on coincidence... toggleList must be an iteratable!
        if self.echo: print "Toggle:", toggleList
        if cell != None:
            toggleList = (toggleList,)
        fileList = []
        # Build list of files to set.
        for toggle in toggleList:
            toggle = self.filterModel.convert_path_to_child_path(toggle)
            self.listStore[toggle][6] = not self.listStore[toggle][6]
            # listStore returns a utf-8 string, we must decode it
            fileList.append((self.listStore[toggle][0].decode('utf-8'), self.listStore[toggle][6]))
        if self.echo: print fileList
        self.db.setSync(fileList)
        self.updateTitle()
        return

    def row_callback(self, treeview, row, column):
        '''Call toggle_callback on a row.'''
        selectedRows = self.selectedRows()
        if selectedRows == []:
            self.toggle_callback(True, row)
        else:
            self.toggle_callback(None, selectedRows)

    def selectedRows(self):
        '''Return list of selected rows by number.'''
        selectedRows = []
        for row in self.tree.get_selection().get_selected_rows()[1:][0]:
            selectedRows.append(row[0])
        return selectedRows

    def updateDBButton_callback(self, button):
        source = self.db.sourceDir()
        print "Updating from %s" % source
        self.opTime, new, removed = self.db.importDir(source, CONFIG_DIR)
        print "Update complete: %.1fs" % self.opTime
        self.view(self.dbFile)

    def deleteSelectedButton_callback(self, button):
        '''Remove selected rows from the DB.'''
        # We have to do the rows in reverse to avoid altering rank number
        for row in self.selectedRows().__reversed__():
            file = self.filterModel[row][0]
            print "Remove:", file
            self.db.removeFile(self.db.sourceDir(), os.path.join(self.db.sourceDir(), file))
            self.listStore.remove(self.listStore.get_iter(row))
        self.db.connection.commit()

    def column_callback(self, column):
        '''Sort currently viewed tracks by column.'''
        print "Sort by %s." % column.get_title()
        return

    def toggleSelectedButton_callback(self, button):
        '''Toggle sync status of all selected rows.'''
        selectedRows = self.selectedRows()
        if selectedRows == []:
            return
        else:
            self.toggle_callback(None, selectedRows)

    def syncAllButton_callback(self, button):
        '''Copy marked files from self.targetDir to self.db.sourceDir'''
        sourceDir = self.db.sourceDir()
        targetDir = self.db.targetDir()
        # If we're missing some info, get it!
        while (not sourceDir or not targetDir):
            r = self.editPrefs()
            if r != gtk.RESPONSE_OK and r != gtk.RESPONSE_APPLY:
                print "Sync: Preferences Aborted."
                return
            sourceDir = self.db.sourceDir()
            if not sourceDir:
                self.errorDialog('Specify a source')
            targetDir = self.db.targetDir()
            if not targetDir:
                self.errorDialog('Specify a target')
        # Cancel if not enough free space
        targetSpace = freeSpace(targetDir)
        copyList, updateList = self.db.copyList(self.visibleSyncFiles())
        #copyList = list(set(self.visibleSyncFiles()).intersection(set(copyList)))
        extraList = self.db.extraList(targetDir)
        unknownList = self.db.unknownList(sourceDir)
        copySize = self.db.fileListSize(copyList)
        updateSize = self.db.fileListSize(updateList)
        extraSize = self.db.fileListSize(extraList)
        if self.echo: print "copySize: %f\nupdateSize: %f\nextraSize: %f\ntargetSize: %f" % (copySize, updateSize, extraSize, targetSpace)
        if targetSpace <= (copySize - extraSize):
            print "Not enough free space on device. %s >= %s" % (copySize, targetSpace)
            self.errorDialog("Not enough free space on device. %s >= %s" % (copySize, targetSpace))
            return
        print "Sync: %s -> %s (%.2f Mib)" % (sourceDir, targetDir, (copySize + updateSize) / 1024.**2)
        if self.echo: print "sync_cb->copyList():", copyList, updateList
        if not copyList and not updateList and not extraList:
            print "Target up to date"
            return
        msg = ''
        if copyList or updateList:
            msg = 'Sync %u file%s?' % (len(copyList) + len(updateList), (len(copyList) + len(updateList) > 1) * 's')
        if extraList:
            if self.echo: print "Extra in target:", extraList
            filename = os.path.join(CONFIG_DIR, self.dbFile + '.' + currentTime() + '-EXTRA_IN_TARGET.bz2')
            self.db.dumpFlatFile(filename, extraList, False) # False = Plain text
            msg += '\nRemove %u file%s?' % (len(extraList), (len(extraList) > 1) * 's')
        if self.dialog(msg).run() == gtk.RESPONSE_NO:
            print "Cancelled"
            return
        errorList = []
        start = time.time()
        if unknownList:
            print "Missing from DB:", unknownList
            filename = os.path.join(CONFIG_DIR, self.dbFile + '.' + currentTime() + '-NOT_IN_DB.bz2')
            self.db.dumpFlatFile(filename, unknownList, False) # False = Plain text
        if extraList:
            self.deleteFiles(targetDir, extraList)
        for file in copyList + updateList:
            abspath = os.path.join(sourceDir, file)
            target = os.path.join(targetDir,file)
            print file
            if not os.path.isdir(os.path.dirname(target)):
                os.makedirs(os.path.dirname(target))
            try:
                shutil.copy2(abspath, target)
            except IOError, e:
                self.errorDialog(str(e.strerror) + ':' + str(e.filename))
                errorList.append(str(e.strerror) + ':' + str(e.filename))
                continue
            except Exception, e:
                errorList.append(e)
                continue
            self.db.updateFile(sourceDir, abspath)
        self.db.connection.commit()
        self.db.mtime(time.time())
        self.opTime = time.time() - start
        print "Sync: complete! %.2fs (%u files)" % (len(copyList) + len(updateList), self.opTime)
        if errorList:
            print "Errors as follows:"
            for err in errorList:
                print err
                self.errorDialog(err)
        self.updateTitle()
        return

    def visibleSyncFiles(self):
        return self.db.syncList([x[0].decode('utf-8') for x in self.filterModel])
        #return list(set([x[0].decode('utf-8') for x in self.filterModel]).intersection(self.db.syncList()))

    def playTrackFromColumn(self):
        r = self.selectedRows()
        cmd = ['xmms']
        if len(r):
            for row in r:
                relpath = self.filterModel[row][0]
                file = os.path.join(self.db.sourceDir(), relpath)
                cmd.append(file)
            subprocess.Popen(cmd)
        return

    def editPrefs(self):
        d = dbPrefsdialog()
        if d.response == gtk.RESPONSE_OK or d.response == gtk.RESPONSE_APPLY:
            dbFile = d.get_Path('DB File')
            if dbFile:
                self.dbFile = dbFile
                self.view(dbFile)
            source = d.get_Path('Source')
            if os.path.isdir(source):
                self.db.sourceDir(source)
                if d.response == gtk.RESPONSE_APPLY:
                        self.opTime, new, removed = self.db.importDir(source, CONFIG_DIR)
                        self.view(self.dbFile)
            target = d.get_Path('Target')
            if target != '':
                if not os.path.isdir(target):
                    if not os.path.exists(target):
                        ans = self.dialog('%s does not exist. Create?' % target).run()
                        if ans == gtk.RESPONSE_YES:
                            os.makedirs(target)
                self.db.targetDir(target)
            force_update_file = d.get_Path('Force Update')
            if force_update_file:
                if os.path.exists(force_update_file):
                    force_update_file = open(os.path.abspath(force_update_file), 'r');
                    lines = force_update_file.readlines()
                    print self.db.targetDir()
                    errors = []
                    for line in [x.strip() for x in lines]:
                        path = os.path.relpath(line, '/-')
                        path = os.path.join(self.db.sourceDir(), path)
                        try:
                            print path
                            os.utime(path, None)
                        except OSError, e:
                            errors.append(e.filename)
                    if errors:
                        self.errorDialog('\n'.join(errors))

        self.updateTitle()
        return d.response

    def openDB(self, dbFile):
        '''Returns a musicDB object connected to dbFile.'''
        return simplesync_db.musicDB(dbFile)

    def deleteFiles(self, targetDir, filelist):
        '''Deletes filelist and empty dirs in filelist from disk.'''
        print "Removing Files:"
        for relpath in filelist:
            abspath = os.path.join(targetDir, relpath)
            dir = os.path.dirname(abspath)
            print abspath
            os.unlink(abspath)
            abspath = os.path.split(abspath)[0]
            while abspath != targetDir:
                try:
                    os.rmdir(abspath)
                    print abspath
                except OSError, e:
                    break
                abspath = os.path.split(abspath)[0]

    class errorDialog(gtk.Window):
        '''Pop-up an error displaying msg.'''
        def __init__(self, msg):
            md = gtk.MessageDialog(self,
                                   gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_ERROR,
                                   gtk.BUTTONS_CLOSE,
                                   msg)
            md.run()
            md.destroy()

    class dialog(gtk.Window):
        '''Pop-up a Yes or No dialog displaying msg.'''
        def __init__(self, msg):
            self.md = gtk.MessageDialog(self,
                                   gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_QUESTION,
                                   gtk.BUTTONS_YES_NO,
                                   msg)
            self.md.xrun = self.md.run

        def run(self):
            r = self.md.xrun()
            self.md.destroy()
            return r

class dbPrefsdialog(gtk.Window):
    '''Dialog box for setting file paths.'''
    def __init__(self):
        self.dialog = gtk.Dialog("File Prefs", self, 0)
        self.dialog.set_default_response(gtk.RESPONSE_CANCEL)
        importButton = self.dialog.add_button(gtk.STOCK_SAVE_AS, gtk.RESPONSE_APPLY)
        importButton.set_label('_Import')
        importButton.set_image(gtk.image_new_from_stock('gtk-save-as', gtk.ICON_SIZE_BUTTON))
        cancelButton = self.dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        okButton = self.dialog.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        self.dialog.action_area.set_layout(gtk.BUTTONBOX_EDGE)
        vbox = gtk.VBox(False, 8)
        vbox.set_border_width(8)
        self.fileEntryGroups = {}
        self.fileEntrySizeGroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
        # Creating the labels, entry boxes, buttons
        for i, name in enumerate(('DB File', 'Source', 'Target', 'Force Update')):
            self.insertEntryGroup(vbox, name, self.fileEntryGroups, i in (1, 2))

        self.dialog.vbox.pack_start(vbox, False, False, 0)
        self.dialog.show_all()
        self.response = self.dialog.run()
        self.dialog.destroy()

    def insertEntryGroup(self, box, name, dict, isFolder = False):
        # Folder is selected if isFolder == True
        sizeGroup = self.fileEntrySizeGroup
        widget = gtk.Entry()
        dict[name] = widget
        label = gtk.Label(name + ':')
        label.set_alignment(1, 0.5)
        label.set_mnemonic_widget(widget)
        sizeGroup.add_widget(label)
        button = gtk.Button(name, gtk.STOCK_OPEN)
        button.connect('clicked', lambda x: self.on_browse_button_clicked(widget, isFolder))
        hbox = gtk.HBox(False, 8)
        for i in (label, widget, button):
            hbox.pack_start(i, False, False, 1)
        box.pack_start(hbox, False, False, 0)

    def on_browse_button_clicked(self, entry, isFolder = False):
        file = self.selectFile(isFolder)
        if file:
            entry.set_text(file)

    def get_Path(self, name):
        path = self.fileEntryGroups[name].get_text()
        path = os.path.expanduser(path)
        if path and not os.path.isabs(path): path = CONFIG_DIR + path
        return path


    def selectFile(self, isFolder):
        '''Return selected file.'''
        if isFolder:
            isFolder = gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER
        else:
            isFolder = gtk.FILE_CHOOSER_ACTION_OPEN
        dialog = gtk.FileChooserDialog("Select...",
                                       None,
                                       isFolder,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_select_multiple(False)
        response = dialog.run()
        try:
            if response == gtk.RESPONSE_OK:
                return dialog.get_filename()
            elif response == gtk.RESPONSE_CANCEL:
                return
        finally:
            dialog.destroy()

def backgroundThread(f):
    print "backgroundThread start"
    def newfunc(*args, **kwargs):
        print "newfunc start"
        class bgThread(threading.Thread):
            def f__init__(self, f):
                print "bgThread Init Start"
                #self.f = f
                threading.Thread.__init__(self)
                print "bgThread Init End"
                return
            def f__call__(self, *args, **kwargs):
                print "__call__ start"
                resp = self.start()
                print "__call__ end"
                return resp
            def frun(self):
                print "Thead start"
                result = self.f(*args, **kwargs)
                print "Thead end"
        print "newfunc end"
        return bgThread(target = f, args = args, kwargs = kwargs).start()
    print "backgroundThread end"
    return newfunc

def freeSpace(path):
    try:
        f = os.statvfs(path)
        # free blocks * block size = bytes
        return f[statvfs.F_FRSIZE] * f[statvfs.F_BAVAIL]
    except OSError, e:
        return 0
    except TypeError, e:
        return 0

def totalSpace(path):
    try:
        f = os.statvfs(path)
        # free blocks * block size = bytes
        return f[statvfs.F_FRSIZE] * f[statvfs.F_BLOCKS]
    except OSError, e:
        return 0
    except TypeError, e:
        return 0

def main():
    #print db.allList()
    window = dbView(CONFIG_DIR + 'ipod.db')
    #window.db.dumpFlatFile(CONFIG_DIR + "ipodDump")
    #window.db.importDir("/media/disk/Music/0-9")
    #window.view('/tmp/ss2.db')
    #window.view('/tmp/simplesync.db')
    gtk.main()
    return 0

if __name__ == '__main__': main()
