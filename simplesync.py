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

import simplesync_db, simplesync_gui

def main():
    db = simplesync_db.musicDB(':memory:')
    db.addDir("/media/disk/Music/0-9")
    window = simplesync_gui.dbView()
    for track in db.allList():
        window.listStore.append((track['title'], track['artist'], track['album'], track['genre'], track['year'],))
    window.tree.set_model(window.listStore)

    simplesync_gui.gtk.main()
    return 0

if __name__ == '__main__': main()
