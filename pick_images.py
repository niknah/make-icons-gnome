import os
# import re
import shutil
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort
import mimetypes
import logging
import argparse
import configparser

app = Flask(__name__, static_folder='static', static_url_path='/static')

# Configuration
FOLDERS = ['make_icons.Oil-Painting-Dark1', 'make_icons.Oil-Painting']  # Update with your folder paths
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
FIRST_FOLDER = FOLDERS[0]
background_white = False
# source_dir = None

def get_stem(path):
    return Path(path).stem


class IndexTheme:
    def __init__(self, folder_path_str):
        config = configparser.ConfigParser()

        folder_path = Path(folder_path_str)
        # Read the index.theme file
        config.read(folder_path / 'index.theme')

        images_by_contextsize = {}
        context_by_images = {}
        self.path_by_images = {}
        images_by_context = {}
        self.config = config
        for path_str,path_info in config.items():
            if 'Context' in path_info:
                context = path_info['Context']
                path_obj = Path(path_str)
                images = self.get_images_in_folder(folder_path / path_obj)
                # print(images)
                images_dict = { get_stem(i) : (path_obj / i) for i in images }

                for i in images:
                    i_path_str = str(path_obj / get_stem(i))
                    context_by_images[i_path_str] = path_info
                    self.path_by_images[i_path_str] = str(path_obj / i)

                contextsize = self.get_contextsize(path_info)
                if contextsize not in images_by_contextsize:
                    images_by_contextsize[contextsize] = {}
                if context not in images_by_context:
                    images_by_context[context] = {}

                images_by_contextsize[contextsize] |= images_dict
                images_by_context[context] |= images_dict
        self.images_by_contextsize = images_by_contextsize
        self.context_by_images = context_by_images
        self.images_by_context = images_by_context

    def get_contextsize(self, path_info):
        context = ""
        if 'Context' in path_info:
            context = path_info['Context']
        else:
            logging.error(f"No context: {path_info}")
        size =path_info['Size']
        return f"{context}x{size}"

    def find_image(self, image, path_info):
        found_path_info = self.context_by_images.get(image, None) # exact path
        if found_path_info is not None:
            return self.path_by_images[image]
        
        # find with same contextsize
        contextsize = self.get_contextsize(path_info)
        stem = get_stem(image)
        found_image = self.images_by_contextsize.get(contextsize, {}).get(stem, None)
        if found_image is None:
            found_image = self.images_by_context.get(path_info.get('Context', ""), {}).get(Path(image).name, None)
        return found_image


    def get_images_in_folder(self, folder_path):
        """Get all image files in a folder recursively"""
        images = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = root / Path(file)
                if file_path.is_symlink():
                    continue
                if file_path.is_file():
                    images.append(os.path.relpath(file_path, folder_path))
        logging.info(f"images: {len(images)}: {folder_path}")
        return sorted(images)


def get_source_images_in_folder(folder_path_str):
    config = configparser.ConfigParser()

    folder_path = Path(folder_path_str)
    # Read the index.theme file
    config.read(folder_path / 'index.theme')

    images_by_context = {}
    for path_str,path_info in config.items():
        if 'Context' in path_info:
            context = path_info['Context']
            path_obj = Path(path_str)
            images = get_images_in_folder(folder_path / path_obj, IMAGE_EXTENSIONS | {'.svg'})
            images_dict = { get_stem(i) : (path_obj / i) for i in images }

            if context not in images_by_context:
                images_by_context[context] = {}

            images_by_context[context] |= images_dict
    return images_by_context

def get_images_in_folder(folder_path, extensions = IMAGE_EXTENSIONS):
    """Get all image files in a folder recursively"""
    images = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = root / Path(file)
            if file_path.is_symlink():
                continue
            if file_path.suffix.lower() in extensions:
                images.append(os.path.relpath(file_path, folder_path))
    logging.info(f"images: {len(images)}: {folder_path}")
    return sorted(images)

def get_all_images():
    """Get images from all folders"""
    all_images = {}
    for folder in FOLDERS:
        folder_obj = Path(folder)
        fullres_folder = folder_obj / "fullres"
        if fullres_folder.is_exists():
            all_images[folder] = get_images_in_folder(fullres_folder)
        elif folder_obj.is_exists():
            all_images[folder] = get_images_in_folder(folder)
        else:
            all_images[folder] = []
    return all_images


def make_table():

    first_theme = IndexTheme(FIRST_FOLDER)

    themes = []
    for folder in FOLDERS[1:]:
        themes.append(IndexTheme(folder))

    images = []
    for image, path_info in first_theme.context_by_images.items():
        row = [first_theme.path_by_images[image]]
        theme : IndexTheme = None
        for theme in themes:
            found_image = theme.find_image(image, path_info)
            
            row.append(found_image)

        images.append(row)
    return images

@app.route('/')
def index():
    images = make_table()
    images = [ row for row in images if row[0].startswith('fullres/') ]
    return render_template(
        'pick_images.html',
        folders=FOLDERS,
        images=images,
        white=background_white,
        )

@app.route('/copy_image', methods=['POST'])
def copy_image():
    source_path = request.form['source_path']
    folder = FOLDERS[int(request.form['folder'])]
    
    # Copy to first folder
    if folder != FIRST_FOLDER:
        dest_path = os.path.join(FIRST_FOLDER, source_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        full_source_path = os.path.join(folder, source_path)
        logging.info(f"copy: {full_source_path} ->  {dest_path}")
        shutil.copy2(os.path.join(folder, source_path), dest_path)
    
    return redirect(url_for('index'))


@app.route('/img/<int:folder>/<path:image_path>')
def serve_image(folder, image_path):
    """Serve image files from folders"""
    # Find which folder contains the image
    folder_path = Path(FOLDERS[folder])
    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type:
        return send_from_directory(folder_path, image_path, mimetype=mime_type)
    else:
        return send_from_directory(folder_path, image_path,)
    abort(404)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Make gnome icons from a prompt.")

    # 2. Add arguments
    parser.add_argument("first_dir", help="Directory to copy to")  # Positional
    parser.add_argument("source_dirs", nargs='*', help="Directories to copy from")  # Positional
    parser.add_argument("--white", action="store_true", help="White background")  # Flag

    parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")  # Flag


    # 3. Parse the command line inputs
    args = parser.parse_args()

    FOLDERS = [args.first_dir] + args.source_dirs
    FIRST_FOLDER = FOLDERS[0]
    background_white = args.white

#    make_table()
    app.run(debug=args.verbose)

