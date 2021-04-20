#!/bin/env python3

import configparser
import re
import sys
import tempfile
import os
import magic
from PySquashfsImage import SquashFsImage
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf

builder = Gtk.Builder()
builder.add_from_file("layout.glade")
window = builder.get_object("window1")
window.set_title("Tiny OPK Viewer")
window.show_all()
textview = builder.get_object("textview1")
textbuffer = textview.get_buffer()
image = builder.get_object("image1")
aboutdialog = builder.get_object('aboutdialog1')

# initialization
textbuffer.set_text("to be loaded")

def load_opk(path):
    filename = path
    opk = SquashFsImage(path)
    image.clear()
    platformset = set()
    desktopno = 0
    platforms = ""
    desktops = dict()
    manuals = dict()
    execs = dict()
    for i in opk.root.children:
        iname = i.getName().decode("utf-8")
        m = re.match(r"(?:[^.]*\.)?([a-zA-Z0-9]+)\.desktop", iname)
        if m is not None:
            desktopno = desktopno + 1
            desktopfile = configparser.ConfigParser(allow_no_value=True, strict=False)
            desktopfile.read_string(i.getContent().decode("utf-8"))
            dset = dict()
            dset['appname'] = desktopfile["Desktop Entry"].get("Name", "", raw=True)
            dset['executable'] = os.path.basename(desktopfile["Desktop Entry"].get("Exec", "<none>", raw=True).split()[0])
            if dset['executable'] in execs:
                execs[dset['executable']].add(iname)
            else:
                execs[dset['executable']] = {iname}
            dset['execid'] = ""
            dset['version'] = desktopfile["Desktop Entry"].get("Version", "", raw=True)
            dset['comment'] = desktopfile["Desktop Entry"].get("Comment", "", raw=True)
            dset['manualpath'] = desktopfile["Desktop Entry"].get("X-OD-Manual", "", raw=True)
            if dset['manualpath'] in manuals:
                manuals[dset['manualpath']].add(iname)
            else:
                manuals[dset['manualpath']] = {iname}
            dset['manual'] = ""
            desktops[iname] = dset
            platformset.add(m.group(1))
        m = re.match(r".+\.png", iname)
        if m is not None:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(i.getContent())
            loader.close()
            image.set_from_pixbuf(loader.get_pixbuf())
    # convert platform set to string
    for p in platformset:
        if platforms == "":
            platforms += p
        else:
            platforms += ", " + p
    for i in opk.root.children:
        iname = i.getName().decode("utf-8")
        if iname in manuals:
            encodings = ["utf-8", "latin_1", "iso8859_2", "cp1250", "cp1252", "utf-16", "utf-32"]
            man = ""
            for e in encodings:
                try:
                    man = i.getContent().decode(e)
                    break
                except:
                    man = "<reading error>"
            for m in manuals[iname]:
                desktops[m]['manual'] = man
        if iname in execs:
            ei = magic.from_buffer(i.getContent())
            for e in execs[iname]:
                desktops[e]['execid'] = ei
            # workaround for libmagic from_file vs from_buffer bug for elves
            #with tempfile.NamedTemporaryFile() as f:
            #    f.write(i.getContent())
            #    execid = magic.from_file(f.name)
    opk.close()
    if platforms == "":
        platforms = "none"
    content = "OPK filename: " + filename + "\n"
    content += "Number of desktop files: " + str(desktopno) + "\n"
    content += "Platforms: " + platforms + "\n\n"
    for key in desktops:
        content += "Desktop file: " + key + "\n"
        if desktops[key]['appname'] == "":
            desktops[key]['appname'] = "none"
        content += "Appname: " + desktops[key]['appname'] + "\n"
        content += "Executable: " + desktops[key]['executable'] + "\n"
        content += "Exec identity: " + desktops[key]['execid'] + "\n"
        if desktops[key]['version'] != "":
            content += "Version: " + desktops[key]['version'] + "\n"
        if desktops[key]['comment'] != "":
            content += "Comment: " + desktops[key]['comment'] + "\n"
        if desktops[key]['manual'] != "":
            content += "Manual:\n" + desktops[key]['manual'] + "\n"
        content += "\n"
    textbuffer.set_text(content)

class Handler:
    def onDestroy(self, *args):
        Gtk.main_quit()

    def onOpen(self, *args):
        dialog = Gtk.FileChooserDialog("Please choose a file", window,
            Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            load_opk(filepath)
        dialog.destroy()

    def onAbout(self, *args):
        aboutdialog.show()

    def onAboutDialogClose(self, *args):
        aboutdialog.hide()

builder.connect_signals(Handler())

if len(sys.argv) == 2:
	load_opk(sys.argv[1])
Gtk.main()
