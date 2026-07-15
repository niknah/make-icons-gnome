
import shutil
import sys
import threading
# import asyncio
import argparse
from types import SimpleNamespace
from pathlib import Path
import logging
from make_icons import MakeIcons
from run_comfy import run_comfy
from flask import Flask, render_template, request  # ,redirect, url_for , send_from_directory
from datetime import datetime

app = Flask(__name__, static_folder='static', static_url_path='/static')


comfyui_path = None
icons_path = None
verbose = False

######

output_final_path = None
output_make_icons_path = None
input_make_icons_path = None

######


# async def async_run_comfy(args):
#     run_comfy(args)
#     return True

run_comfy_task = None
thread = None

@app.route('/running_comfy')
def is_running_comfy():
    return {"running_comfy": (thread is not None and thread.is_alive()) }
#    return {"running_comfy": (True if run_comfy_task is not None and not run_comfy_task.done() else False )}

@app.route('/wait_comfy')
def wait_comfy():
    return render_template('wait_comfy.html')

@app.route('/run_comfy_page')
def run_comfy_page():
    return render_template('run_comfy.html')

@app.route('/do_run_comfy', methods=['POST'])
def do_run_comfy():
    global thread
#    global run_comfy_task

    run_comfy_args_dict = {
        "comfy_path" : comfyui_path,
        "prompt" : request.form['prompt'],
        "seed" : request.form['seed'],
    }
    run_comfy_args = SimpleNamespace(**run_comfy_args_dict)

    # 2. Pass arguments straight into the function call inside create_task
    # run_comfy_task = asyncio.run(async_run_comfy(run_comfy_args))

    thread = threading.Thread(target=run_comfy, args=(run_comfy_args,), daemon=True)

    thread.start()

    return { "ok": True }
#    return redirect(url_for('wait_comfy'))


######

def make_icons_empty_args():
    args_dict = {
        "icons_path":str(icons_path),
        "comfyui_path": str(comfyui_path),
        "verbose": verbose,
        "transparency_range": None,
        "black": None,
        "white": None,
        "brightness": 1,
        "min_size": 48,
        "fullres_size": 0,
        "draw_size": 0,
        "rows_per_file": None,
        "alt_output": None,
    }
    return SimpleNamespace(**args_dict)

@app.route('/')
def make_icons_page():
    return render_template('make_icons.html',
       comfyui_path=comfyui_path,
       icons_path=icons_path,
       output_final_path=output_final_path
       )


#def background_task(args):
#    make_icons(args)
#
#
#def start_background_task(args):
#    # Create the thread
#    thread = threading.Thread(target=background_task, args=(args,))
#
#    # Setting daemon=True stops the thread automatically when the main script ends
#    thread.daemon = True
#
#    # Start the background execution
#    thread.start()






@app.route('/do_make_icons', methods=['POST'])
def do_make_icons():
    args = make_icons_empty_args()

    args.draw_size = int(request.form['draw_size'])
    args.min_size = int(request.form['min_size'])
    args.white = True if request.form.get('white', False) else False

    transparency_range = [
        request.form.get('transparency_range_min', 0 ),
        request.form.get('transparency_range_max', 0)
    ]
    if(transparency_range[0] !="" and transparency_range[1] !=""):
        transparency_range[0] = int(transparency_range[0])
        transparency_range[1] = int(transparency_range[1])
        if(transparency_range[0] > 0 and transparency_range[1] > 0):
            args.transparency_range = f"{transparency_range[0]},{transparency_range[1]}"

#    start_background_task(args):

    # Deletes the directory and everything inside it
    postprocess = request.form.get('postprocess',None)
    symlink_needed = False
    if postprocess:
        from copy_links import copy_links
        if not sys.platform.startswith("win"):
            copy_links(icons_path, output_final_path, False)
        else:
            symlink_needed = True
    else:
        shutil.rmtree(output_final_path, ignore_errors=True)
        if output_make_icons_path.exists():
            iso_date = datetime.now().isoformat().replace(":","")
            new_dir = str(output_make_icons_path) + f".{iso_date}"
            output_make_icons_path.rename(new_dir)
        # we maybe running it again because comfyui aborted
        # shutil.rmtree(comfyui_path / "input/make_icons", ignore_errors=True)

    make_icons = MakeIcons()
    make_icons.make_icons(args)

    return { "ok": True, "symlink_needed" : symlink_needed }


@app.route('/clean_icons')
def clean_icons():
    shutil.rmtree(output_make_icons_path, ignore_errors=True)
    shutil.rmtree(output_final_path , ignore_errors=True)
    shutil.rmtree(input_make_icons_path , ignore_errors=True)
    return { "ok": True }



######

# @app.route('/brightness')
# def brightness():
#     return render_template('brightness.html')
# 
# @app.route('/do_brightness', methods=['POST'])
# def do_brightness():
#     # remove output final
#     icons_final = comfyui_path / "output/make_icons_final"
# 
#     # Deletes the directory and everything inside it
#     shutil.rmtree(str(icons_final), ignore_errors=True)
# 
#     args = make_icons_empty_args()
# 
# #    args.draw_size = int(request.form['draw_size'])
# #    args.min_size = int(request.form['min_size'])
# 
#     args.brightness = float(request.form['brightness'])
#     make_icons(args)
# 
#     return render_template('done.html')

######

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Make gnome icons from a prompt.")

    # 2. Add arguments
    parser.add_argument("icons_path", help="Icons to start from")  # Positional
    parser.add_argument("comfyui_path", help="ComfyUI")  # Positional

    parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")  # Flag

    # 3. Parse the command line inputs
    args = parser.parse_args()

    comfyui_path = Path(args.comfyui_path)
    if( not comfyui_path.is_dir()
        or not (comfyui_path / "input").is_dir()
        or not (comfyui_path / "output").is_dir()
    ):
        logging.error(f"Not a ComfyUI folder {str(comfyui_path)}")
        exit(1)

    icons_path = Path(args.icons_path)
    if( not icons_path.is_dir()):
        logging.error(f"Not a icons_path folder {str(icons_path)}")
        exit(1)

    output_final_path = comfyui_path / "output/make_icons_final"
    output_make_icons_path = comfyui_path / "output/make_icons"
    input_make_icons_path = comfyui_path / "input/make_icons"

    verbose = args.verbose

    app.run(debug=args.verbose)
