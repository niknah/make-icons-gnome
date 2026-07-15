import gi
import argparse

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

icon_name = "utilities-terminal"  # Change this to any valid icon name
icon_size = 32
icon_lookup_flags = 0

def on_activate(app):
    # 1. Create the main application window
    window = Gtk.ApplicationWindow(application=app)
    window.set_title("Icon Display")
    win_size=max(icon_size, 256)
    window.set_default_size(win_size, win_size)

    # 2. Look up the icon using the default system theme
    icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())

    paintable = icon_theme.lookup_icon(
        icon_name,
        fallbacks=None,
        size=icon_size,             # Icon size in pixels
        scale=1,
        direction=Gtk.TextDirection.NONE,
        flags=icon_lookup_flags,
    )

    # 3. Create the Image widget from the icon
    image = Gtk.Picture.new_for_paintable(paintable)
    image.set_halign(Gtk.Align.CENTER)
    image.set_valign(Gtk.Align.CENTER)
    image.set_content_fit(Gtk.ContentFit.CONTAIN)

    grid = Gtk.CenterBox()
    grid.set_center_widget(image)

    window.set_child(grid)
    window.present()




if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Make gnome icons from a prompt.")

    # 2. Add arguments
    parser.add_argument("icon", help="name of icon")  # Positional
    parser.add_argument("size", type=int, nargs='?', default=32, help="size of icon")  # Positional
    parser.add_argument("--flags", type=str, help="Flags")  # Flag
    args = parser.parse_args()
    icon_size = args.size
    icon_name = args.icon
    if args.flags:
        for flag in args.flags.split(','):
            icon_lookup_flags |= Gtk.IconLookupFlags[flag]

    # Initialize and run the application
    app = Gtk.Application(application_id="org.example.IconViewer")
    app.connect("activate", on_activate)
    app.run(None)
