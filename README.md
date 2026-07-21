

This generates new gnome icons from an existing set based on a prompt.

If you are not making gnome icons, just wish to bulk edit some images use [bulk\_edit\_workflow](bulk_edit_workflow.json)

[Example icons](https://www.gnome-look.org/u/niknah/)

[Video Instructions](https://youtu.be/THG79GpO464)



## Requirements

nVidia video card with 16gb+ VRAM.  It'll work with less VRAM but it'll be slower.



## To install

* Install ComfyUI, load the workflow from `static/make_icons_workflow.json`
* Click Extensions or Manager ->  Install missing nodes
* Also install "Queued Reboot" nodes.
* Then download the models show on the right panel.
* In Windows install GTK: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
* `pip install -r requirements.txt`
* Start the web interface `python make_icons_web.py <SourceIcons> <ComfyUIPath>`
* http://localhost:5000/



## The command line way

### If you have ComfyUI on Linux.  Change the Yaru path below to whatever icon set you want to base the icons on

* Get your prompt ready.  Ask chatbots "Please describe XXX graphic style". Copy the paragraphs that you like.  Remove references to colors if you don't want single colors.  Remove references to shapes, objects, it may override the shapes on the icon.
* `python make_icons.py /usr/share/icons/Yaru <ComfyUIPath>`
* In ComfyUI: Run the `make_icons_workflow.json` use the `make_random_icons.csv`.  Change the prompt to what you want it to look like.  This part is most important.
* `python run_comfy.py <ComfyUIPath> "YourPrompt"`
* `python make_icons.py /usr/share/icons/Yaru <ComfyUIPath>`
* `python copy_links.py /usr/share/icons/Yaru <ComfyUIPath>/output/make_icons_final`
* Copy the icons folder from `<ComfyUIPath>/output/make_icons_final` to `~/.icons/YourIconThemeName`
* Change the theme with Gnome Tweaks.


### If you have ComfyUI on Windows

ComfyUI works best with a nVidia video card.  Most people have one on their gaming PC which is usually in windows.

On Linux.  Run

```
cd <PathToIcons>
find -type f >/tmp/icon_files.txt
tar -czf /tmp/icon_files.tgz -T /tmp/icon_files.txt
```

Copy the `/tmp/icon_files.tgz` to Windows and extract it.


* On Windows. Run `python make_icons.py <SourceIconFiles> <ComfyUIPath>`
* Optional: Run the `make_icons_workflow.json` in ComfyUI to test your prompt
* Run `python run_comfy.py --seed=2 <ComfyUIPath> "YourPrompt"`
* Close the ComfyUI browser window because it'll overheat your browser.
* Folder with the icons will be here `ComfyUI/output/make_icons_final`.  Copy it back to Linux.
* In Linux to copy the symlinks from the original theme run.  `python copy_links.py <PathToMakeIconsFinal> make_icons_final`
* Copy the `make_icons_final` folder to `~/.icons/YourNewIconsName`
* Go to Gnome tweaks, appearance and load up your new icons




## To change brightness

```
rm -rf <ComfyUIPath>/make_icons_final
python make_icons.py --brightness=2 /usr/share/icons/Yaru <ComfyUIPath>
```

## Pick best icons

* Make several icon sets with different `--seed ?` settings.
* Copy the first icon set so you have a back up.
* Run
```
python pick_images.py NewIconsFolder NewIconsFolderBackup NewIconsDifferentSeed1 NewIconsDifferentSeed2  # as many different seeds/prompts as you like
```
* Visit http://localhost:5000/
* Click on the image you like to copy it to the first one


## Details

The process is...

* `make_icons.py` Copies the original icons as png to `ComfyUI/input/make_icons`
* ComfyUI will make the `ComfyUI/output/make_icons`
* `make_icons.py` adds transparency from `ComfyUI/output/make_icons` to `ComfyUI/output/make_icons_fullres`
* `make_icons.py` resizes `ComfyUI/output/make_icons_fullres` to `ComfyUI/output/make_icons_final`

Do any editing of the transparency in `ComfyUI/output/make_icons/fullres`.  Run `make_icons.py` again to copy the fullres version into the other versions.

Delete these folders when you want to run it again
`ComfyUI/input/make_icons`
`ComfyUI/output/make_icons*`



## Options

`make_icons.py`
| Option |  Description |
| -- | -- |
| `--draw-size=?` |  width / height pixels to send to the drawing process in ComfyUI |
| `--transparency-range=min,max` | The range is 0-255.  32,64 means pixels below 32 is inivisible, pixels 32-64 are semi transparent.  Above 64 is sold |
| `--rows-per-file=rows` | Used when you don't have enough RAM to run a big batch in ComfyUI.  A lower number will use up less memory each run. |
| `--min-size=?` |  Set this to 0 if you want to use the output for small icons.  A lot of prompts draw complex things that don't look good.  |


## Tips


* If you have a prompt that's making detailed icons that can't be seen in 16x16.
Go back to the original and copy the old 16x16 folder.

* If you have ComfyUI in windows.  You can access it from wsl by adding this to `%USERPROFILE%/.wslconfig.ini`
```
[wsl2]
networkingMode=mirrored
```
Then run `wsl --shutdown` to restart it.


* If you wish to change the workflow.  Load `make_icons_workflow.json` into ComfyUI, use File -> export API -> overwrite `make_icons_workflow_api.json`

* Use the nvfp4 version of Flux klein if you have a 5xxx series nVidia card.

* Can be used for any folder with images in it.  Doesn't have to be an icon set.
```
python make_icons.py <PathWithImages> <ComfyUIPath>
python run_comfy.py <ComfyUIPath> "YourPrompt"
```


## Sizes

Use `make_icons.py --draw-size=xx` to set the size.

If your icons are visually ok in small resolution use `make_icons.py --min-size=0` to use it for all icons.  
Or edit `index.theme`, at the bottom change the `fullres/` sections so that `MinSize=xx` is small.


## Other tools

* Shows an icon by name: `python show_icon.py <IconName> <PixelSize>`
* Make a bunch of empty files in the current directory to view file type icons `make_mime_types_examples.py YourIconSet/fullres/MimeTypes`
* Check that all the icons have been done.  `diff_icons.sh <SourceIconSet> <YourNewIconSet>`



