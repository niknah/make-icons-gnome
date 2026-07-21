#!/usr/bin/env python3


import os
import re
import sys
import random
import shutil
from pathlib import Path
from collections import defaultdict
from PIL import Image, ImageEnhance, ImageOps #, ImageFilter
import traceback
import subprocess
import csv
import argparse
import logging
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
from commentedconfigparser import CommentedConfigParser



default_size = 192
draw_size = 0

class IconsPath:
    root_path: Path
    path: Path
    resolution: int
    max_size: int
    scale: int
    scalable: bool
    context: str

    def __init__(self, path : Path, root_path : Path, options = {}):
        self.root_path = root_path
        self.path = path
        self.scale = 1
        self.options = options
        self.scalable = True if options.get('type', "").lower() == 'scalable' else False

        self.max_size = self.resolution = int(options.get('size', default_size))
        if 'maxsize' in self.options:
            self.max_size = int(self.options['maxsize'])

        if 'context' in options:
            self.context = options['context']
        else:
            self.context = "all"

        if self.resolution == 0:
            (w, h) = self.extract_resolution(str(path))
            self.resolution = w

    def extract_number(self, name: str) -> int:
        numbers = self.extract_resolution(name)

        return numbers[0]*numbers[1]

    def extract_resolution(self, name: str) -> (int, int):
        """Return the last integer found in *name*, or -inf if none."""
        numbers_x = re.search(r"(\d+)x(\d+)\@(\d+)x", name)
        if numbers_x is not None:
            multiply = int(numbers_x.group(3))
            return ( int(numbers_x.group(1)) * multiply, int(numbers_x.group(2)) * multiply )

        numbers = re.search(r"(\d+)x(\d+)", name)
        if numbers is not None:
            return ( int(numbers.group(1)), int(numbers.group(2)) )

        numbers = re.search(r"[\\/](\d+)[\\/]", name)
        if numbers is not None:
            return ( int(numbers.group(1)), int(numbers.group(1)) )

        return (0,0)

    def relative_path(self):
        return self.path.relative_to(self.root_path)

    def get_max_resolution(self):
        comfy_width = max(self.resolution, self.max_size, default_size)
        comfy_height = max(self.resolution, self.max_size, default_size)

        return (comfy_width, comfy_height)

    def get_draw_size(self):
        if draw_size > 0:
            if self.resolution > draw_size:
                comfy_height = comfy_width = self.resolution
            else:
                comfy_height = comfy_width = draw_size
        else:
            (comfy_width, comfy_height) = self.get_max_resolution()
        return (comfy_width, comfy_height)



class FoundIcon:
    def __init__(self, icons_path : IconsPath, path : Path):
        self.icons_path=icons_path
        self.path = path

    def full_path(self):
        return self.icons_path.path / self.path

    def relative_path(self):
        return self.icons_path.relative_path() / self.path



class MakeIcons:
    # size to use for editing with ComfyUI / Klein
    def __init__(self):
        self.rows_per_file = 800
        self.min_size = 0
        self.fullres_size = 0  # force the fullres to be this size
        self.transparency_range = [ 32, 64 ]
        self.transparency_black = True
        self.brightness=1
        self.alt_output_paths = []


    def add_index_theme_path(self, last_path, root_path, options):
        if last_path is None or 'size' not in options:
            return None
        icons_path = IconsPath(last_path, root_path, options)
        return icons_path

    def read_index_theme(self, index_path : Path):
        all_icons_paths = []

        # Read the index.theme file
        config = CommentedConfigParser()
        config.optionxform = str

        config.read(index_path)
        index_dir = index_path.parent

        for path_str,path_info in config.items():
            if 'Type' not in path_info or 'Context' not in path_info:
                continue

            last_path = index_dir / Path(path_str)
            options = { k.lower(): v for k, v in path_info.items() }
            all_icons_paths.append(self.add_index_theme_path(last_path, index_dir, options))

        return all_icons_paths






    def find_folders(self, root: Path) -> list[Path]:
        """Return immediate sub-folders of *root* that contain at least one digit."""
        return [
            IconsPath(p, root_path=root) for p in root.iterdir()
            if p.is_dir()
        ]



    def group_svgs_by_name(self, folders: list[IconsPath]) -> dict[str, list[FoundIcon]]:
        """
        Build a mapping  stem -> [path, path, ...]  for every .svg found inside
        *folders*.  Only the stem (filename without extension) is used as key so
        that files with the same name in different folders are grouped together.
        """
        groups: dict[str, list[FoundIcon]] = defaultdict(list)
        for folder in folders:
            if not folder.path.exists():
                # maybe a symlink folder.  Skip
                continue
            for svg in folder.path.iterdir():
                if not svg.is_file() or svg.stat().st_size == 0:
                    continue
                if svg.suffix in ('.png','.svg'):
                    name = f"{folder.context}/{svg.stem}"
                    groups[name].append(FoundIcon(folder, svg.relative_to(folder.path)))
        return groups


    def best_svg(self, paths: list[FoundIcon]) -> Path:
        """Pick the SVG that lives in the folder with the highest number."""
        return max(paths, key=lambda p: (
                p.icons_path.resolution +
                # prefer svg
                (1000000000 if p.path.suffix == '.svg' else 0) +
                # prefer scalable
                (10000000000 if p.icons_path.scalable else 0)
            )
        )


    # ---------------------------------------------------------------------------
    # Conversion back-ends
    # ---------------------------------------------------------------------------

    def convert_with_cairosvg(self, found_icon: FoundIcon, png_path: Path) -> None:
        (comfy_width, comfy_height) = found_icon.icons_path.get_draw_size()

        import cairosvg  # type: ignore
        found_path = found_icon.full_path()
        cairosvg.svg2png(
            url=str(found_path),
            write_to=str(png_path),
            output_width=comfy_width,
            output_height=comfy_height
        )
        pil_img_orig = Image.open(png_path)
        pil_img = pil_img_orig.copy()

        datas = pil_img_orig.get_flattened_data()

        if self.transparency_black:
            bg_color=(0, 0, 0, 255)
        else:
            bg_color=(255, 255, 255, 255)
        new_data = []
        for item in datas:
            # Check if the alpha value (item[3]) is transparent (0)
            if item[3] == 0:
                # Replace with a solid color (e.g., Solid Red)
                new_data.append(bg_color)
            else:
                new_data.append(item)
        # 3. Update the image data and save
        pil_img.putdata(new_data)

        new_data = []
        (_, percent_transparent) = self.make_transparent(pil_img)
        if percent_transparent >= 0.95:
            logging.warning(f"Nothing much visible, inverting image png: {png_path}")
            for item in datas:
                if item[3] == 0:
                    new_data.append(bg_color)
                else:
                    new_data.append((255-item[0], 255-item[1], 255-item[2], item[3]))
            # 3. Update the image data and save
        else:
            for item in datas:
                if item[3] == 0:
                    new_data.append(bg_color)
                else:
                    new_data.append(item)

        pil_img.putdata(new_data)
        pil_img.save(png_path)

    def get_transparent_pixels_percent(self, pil_img):
        grayscale_img = pil_img.convert('L')
        histogram = grayscale_img.histogram()
        total_pixels = pil_img.width * pil_img.height
        if self.transparency_black:
            total_not_transparent = sum(histogram[self.transparency_range[1]: ])
        else:
            total_not_transparent = sum(histogram[:self.transparency_range[0]])

        percent_not_transparent = total_not_transparent / total_pixels
        return percent_not_transparent

    def convert_with_libsvg(self, found_icon: FoundIcon, png_path: Path) -> None:
        (comfy_width, comfy_height) = found_icon.icons_path.get_draw_size()

        drawing = svg2rlg(found_icon.full_path())
        factor_width = comfy_width / drawing.width
        factor_height = comfy_height / drawing.height
        drawing.width = comfy_width
        drawing.height = comfy_height

        drawing.scale(factor_width, factor_height)
        background = 0x000000 if self.transparency_black else 0xffffff


        # pil_img = Image.new("RGBA", (comfy_width, comfy_height))

        # 3. Draw the ReportLab drawing onto the PIL image
        pil_img = renderPM.drawToPIL(drawing, bg=background)
        (_, percent_transparent) = self.make_transparent(pil_img)

        if percent_transparent >= 0.95:
            logging.warning(f"Fix transparent background, revert: {png_path}")

            # mostly transparent.  Revert the background
            background = 0xffffff if self.transparency_black else 0x000000
            pil_img = renderPM.drawToPIL(drawing, bg=background)
            pil_img = ImageOps.invert(pil_img)

            # mostly transparent.  Revert the image
            # pil_img = Image.new("RGBA", (comfy_width, comfy_height))
            # renderPM.drawToPIL(drawing, pil_img)
            # invert_image(pil_img, background)

    #        if get_transparent_pixels_percent(pil_img) < 0.02:
    #            logging.error(f"Image does not have much transparent background: {png_path}")

        # Now 'pil_img' is a standard Pillow Image object
        pil_img.save(str(png_path))

        # renderPM.drawToFile(drawing, str(png_path), fmt="PNG")
        #png_bytes = renderPM.drawToString(drawing, fmt="PNG")
        #img = Image.open(io.BytesIO(png_bytes))
        #return img


    #def convert_with_inkscape(svg_path: Path, png_path: Path, dpi: int = 300) -> None:
    #    subprocess.run(
    #        ["inkscape", "--export-type=png", f"--export-dpi={dpi}",
    #         f"--export-filename={png_path}", str(svg_path)],
    #        check=True, capture_output=True,
    #    )
    #
    #
    #def convert_with_rsvg(svg_path: Path, png_path: Path, dpi: int = 300) -> None:
    #    subprocess.run(
    #        ["rsvg-convert", "-d", str(dpi), "-p", str(dpi),
    #         "-o", str(png_path), str(svg_path)],
    #        check=True, capture_output=True,
    #    )


    def get_converter(self):
        """Return the first available conversion function."""
        try:
            # import cairosvg  # noqa: F401
    #        return convert_with_libsvg
            return self.convert_with_cairosvg
        except ImportError:
            pass
    #    if shutil.which("inkscape"):
    #        return convert_with_inkscape
    #    if shutil.which("rsvg-convert"):
    #        return convert_with_rsvg
        raise RuntimeError(
            "No SVG-to-PNG converter found.\n"
            "Install one of:\n"
            "  pip install cairosvg\n"
            "  apt install inkscape\n"
            "  apt install librsvg2-bin"
        )



    def png_to_svg(self, in_file, out_file):
        vtracer_bin = shutil.which("vtracer")
        if vtracer_bin is not None:
            result = subprocess.run(
                [vtracer_bin, "--mode", "polygon", "--input", in_file, "--output", out_file ],
                capture_output=True,
                text=True,
                check=True
                )
            return result
        return None


    def resize_and_save(self, image: Image, mtime, paths: list[FoundIcon], dest_path : Path):
        path : FoundIcon
        resized=0
        for path in paths:
            relative_path = path.icons_path.relative_path()
            dest_file = dest_path / relative_path / path.path

            if path.icons_path.resolution < self.min_size:
                # too small, just copy
                if not dest_file.exists() or mtime > dest_file.stat().st_mtime:
                    logging.debug(f"too small: {dest_file}, resolution: {path.icons_path.resolution}, {path.full_path()}, {dest_file}")
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path.full_path(), dest_file)
                continue

            dest_file = dest_file.with_suffix(".png")

            if dest_file.exists():
                if mtime < dest_file.stat().st_mtime:
                    # resized destination image is newer
                    continue

            logging.debug(f"resize_and_save {path.path}")

            width = height = path.icons_path.resolution
            logging.debug(f"resize_and_save width: {width}")
            if width == 0:
                continue

            img_copy = image.copy()

            # 3. Resize the duplicate
            resized_img = img_copy.resize((width, height), Image.Resampling.LANCZOS)

            dest_file.parent.mkdir(parents=True, exist_ok=True)
            logging.debug(f"resize_and_save dest_file: {dest_file}")

            resized_img.save(str(dest_file))
            resized+=1
        return resized


    # The AI rembg type things haven't worked well for me.
    # They remove more than they should even at the lowest settings.
    def make_transparent(self, img):
        if self.transparency_range is None:
            return (img, None)

        rgba = img.convert("RGBA")
        datas = rgba.get_flattened_data()
        transparency_multi = 255 / (self.transparency_range[1] - self.transparency_range[0])


        newData = []
        has_trans = 0
        for item in datas:
            not_trans = False

            if self.transparency_black:
                for c in range(0,3):
                    if(
                        (item[c] > self.transparency_range[1])
                    ):
                        not_trans = True
            else:
                for c in range(0,3):
                    if(
                        (item[c] < self.transparency_range[0])
                    ):
                        not_trans = True

            if not not_trans:
                # background_color = round(avg_color)
                if self.transparency_black:
                    alpha =  ( item[0] - self.transparency_range[0]) * transparency_multi
                else:
                    alpha =  (self.transparency_range[1] - item[0] ) * transparency_multi
                alpha = min( max(round(alpha), 0), 255)

                newData.append((item[0], item[1], item[2], alpha))
                has_trans += 1
            else:
               newData.append(item)

        percent_transparent = has_trans / len(datas)

        rgba.putdata(newData)
        return (rgba, percent_transparent)



    def make_index_theme(self, index_path : Path, dest_index_path : Path, fullres_paths, contextes):
        config = CommentedConfigParser()
        config.optionxform = str

        # Read the index.theme file
        config.read(index_path)

        icon_theme = config['Icon Theme']

        scaled_directories = icon_theme.get('ScaledDirectories', "")
        if scaled_directories != "":
            scaled_directories += ","
        scaled_directories += ",".join(fullres_paths)

        icon_theme['ScaledDirectories'] = scaled_directories


        # find largest scalable icons
        largest_scalable_by_context = {}

        for path_str,path_info in config.items():
            if 'Type' not in path_info or 'Context' not in path_info:
                continue

            section_type = path_info['Type']
            if section_type != 'Scalable':
                continue

            context = path_info['Context']

            section_size = int(path_info['Size'])
            set_largest = False
            if section_size <= self.min_size:
                if context in largest_scalable_by_context:
                    largest_size  = int(largest_scalable_by_context[context][1]['Size'])
                    if section_size > largest_size:
                        set_largest = True
                else:
                    set_largest = True
                if set_largest:
                    largest_scalable_by_context[context] = (path_str, path_info)

        min_size1_str = f"{self.min_size - 1}"
        for path_str,path_info in config.items():
            if 'Type' not in path_info or 'Context' not in path_info:
                continue

            # Keep scalable directories.  Reduce max size
            section_type = path_info['Type']
            context = path_info['Context']


            if 'MaxSize' in path_info:
                section_max_size = int(path_info['MaxSize'])
                if section_max_size >= self.min_size:
                    path_info['MaxSize'] = min_size1_str

            if 'Size' in path_info:
                section_size = int(path_info['Size'])
                if section_size >= self.min_size:
                    path_info['Size'] = min_size1_str

            if 'MinSize' in path_info:
                section_min_size = int(path_info['MinSize'])
                if section_min_size >= self.min_size:
                    path_info['MinSize'] = min_size1_str

            if section_type == 'Scalable':
                (largest_path, largest_path_info) =  largest_scalable_by_context[context]
                if path_str == largest_path:
                    # use this for everything below min_size
                    path_info['MinSize'] = "0"


        for context in contextes.keys():
            size = contextes[context]
            if self.fullres_size > 0:
                size = self.fullres_size
            new_section = {
                'Context': context,
                "Size": str(size),
                "Type": "Scalable",
            }

            if self.min_size > 0:
                new_section['MinSize'] = str(self.min_size)

            config[f"fullres/{context}"] =  new_section


        with open(dest_index_path, "w", encoding="utf-8") as configfile:
            config.write(configfile, space_around_delimiters=False)

        return




    def resize_image(self, img, size):
        return img.resize((size, size), Image.LANCZOS)


    def main(self, search_root: str | Path = ".", comfy_path : Path="ComfyUI") -> None:
        input_icons_path = comfy_path / Path("input/make_icons")
        output_icons_path = comfy_path / Path("output/make_icons")

        dest_icons_path = comfy_path / Path("output/make_icons_final")
        fullres_icons_path = comfy_path / Path("output/make_icons_final/fullres")

        if not dest_icons_path.exists():
            dest_icons_path.mkdir(parents=True, exist_ok=True)

        out_rows = []

        root = Path(search_root).resolve()
        if not root.is_dir():
            sys.exit(f"Error: '{root}' is not a directory.")

        logging.info(f"Scanning: {root}\n")

        index_path = root / "index.theme"
        if index_path.exists():
            folders = self.read_index_theme(index_path)

        else:
            logging.warning("index.theme does not exist.  Going through all files.")
            folders = self.find_folders(root)

        if not folders or len(folders)==0:
            sys.exit("No sub-folders found.")


        groups : dict[str, list[FoundIcon]] = self.group_svgs_by_name(folders)
        if not groups:
            sys.exit("No .svg files found in any numbered folder.")

        converter = self.get_converter()

        ok = failed = 0

        contextes : dict[str, int] = {}

        for stem, paths in sorted(groups.items()):
            chosen : FoundIcon = self.best_svg(paths)

            chosen_path : Path = chosen.full_path()

            relative_file_svg : Path = chosen_path.relative_to(root)
            relative_file : Path = relative_file_svg.with_suffix(".png")
            png_path : Path = output_icons_path / relative_file
            input_path : Path = input_icons_path / relative_file

            (width, height) = chosen.icons_path.get_draw_size()

            contextes[chosen.icons_path.context] = width
            fullres_icon_file = fullres_icons_path /  Path(chosen.icons_path.context) / relative_file.name # / Path(dest_icon_file.name)

            logging.debug(f"icon: [{stem}] {fullres_icon_file}")

            try:
                input_path.parent.mkdir(parents=True, exist_ok=True)
                if not input_path.exists():
                    if chosen.path.suffix == '.svg':
                        converter(chosen, input_path)
                    else:
                        shutil.copy2(chosen_path, input_path)
                    size_kb = input_path.stat().st_size / 1024
                    logging.debug(f"    result : OK  ({size_kb:.1f} KB) {input_path}\n")

                if png_path.exists() and png_path.stat().st_mtime > input_path.stat().st_mtime:
                    logging.debug(f'Using best resolution: {chosen_path}')
                    logging.debug(f'png_path: {png_path}')
                    logging.debug(f'png_path dest: {fullres_icon_file}')
                    png_path_mtime = png_path.stat().st_mtime
                    trans_image = None

                    png_image = Image.open(png_path)
                    trans_image = png_image

                    (trans_image, percent_transparent) = self.make_transparent(png_image)
                    if percent_transparent <0.05:
                        logging.info(f"Not much transparency to remove, use --black or --white? {stem}, percent transparent: {percent_transparent*100:.1f}%")
                    elif percent_transparent >=0.95:
                        logging.info(f"Mostly transparent. --transparency-range? {stem}, percent transparent: {percent_transparent*100:.1f}%")

                    if self.brightness != 1:
                        brightness_enhancer = ImageEnhance.Brightness(trans_image)
                        trans_image = brightness_enhancer.enhance(self.brightness)

                    if (
                        not fullres_icon_file.exists() or
                        png_path_mtime > fullres_icon_file.stat().st_mtime
                    ):
                        # comfy has done this file, copy it to final

                        fullres_image = trans_image.copy()
                        if self.fullres_size > 0:
                            fullres_image = self.resize_image(fullres_image, self.fullres_size)

                        fullres_icon_file.parent.mkdir(parents=True, exist_ok=True)
                        fullres_image.save(fullres_icon_file)
                    else:
                        trans_image = Image.open(fullres_icon_file)

                        ok += 1

                    fullres_icon_file_mtime = fullres_icon_file.stat().st_mtime
                    self.resize_and_save(trans_image, fullres_icon_file_mtime, paths, dest_icons_path)
                elif chosen.icons_path.resolution >= self.min_size:
                    logging.debug(f'png_path {png_path}')
                    png_path.parent.mkdir(parents=True, exist_ok=True)
                    # comfy needs to make this one
                    csv_icon_path = Path("make_icons") / relative_file
                    out_rows.append(['i2i', csv_icon_path, csv_icon_path.with_suffix("") , width])
                else:
                    logging.debug(f'Use original below min_size: {chosen.icons_path.resolution} < {self.min_size}: {chosen_path}')
                    for path in paths:
                        path_relative_svg : Path = path.relative_path()
                        dest_svg : Path = dest_icons_path / path_relative_svg
                        dest_png : Path = (dest_icons_path / path_relative_svg).with_suffix('.png')
                        src_svg : Path = path.icons_path.root_path / path_relative_svg

                        if dest_png.exists():
                            continue

                        if not src_svg.exists():
                            logging.error(f"Could not find original: {src_svg}")
                        elif (
                            not dest_svg.exists() or 
                            dest_svg.stat().st_mtime < src_svg.stat().st_mtime
                        ):
                            logging.debug(f"copy small icon: {src_svg} -> {dest_svg}")
                            dest_svg.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src_svg, dest_svg)

            except Exception as exc:
                traceback.print_exc()
                logging.error(f"    result : FAILED – {stem}, {input_path}, {exc}\n")
                failed += 1

        # wipe existing csv
        input_path : Path = comfy_path / Path('input')
        for old_csv in input_path.glob('make_icons*.csv'):
            os.unlink(old_csv)

        # make new csv
        start_row : int = 0
        file_upto : int = 1
        header_row = [['workflow', 'source path', 'dest path(no extension)', 'size']]
        while start_row < len(out_rows):
            csv_path = input_path / Path(f'make_icons{file_upto}.csv')
            with csv_path.open('w', newline='') as file:
                writer = csv.writer(file)
                writer.writerows(header_row + out_rows[start_row:(start_row + self.rows_per_file)])  # Write all rows at once
            start_row += self.rows_per_file
            file_upto += 1


        # make random sample to test
        random_out_rows = out_rows.copy()
        random.shuffle(random_out_rows)
        random_csv_path = input_path / Path('make_random_icons.csv')
        # random-csv_path.unlink(missing_ok=True)
        if len(random_out_rows) > 0:
            with random_csv_path.open('w', newline='') as file:
                writer = csv.writer(file)
                random_out_rows = random_out_rows[0:25]
                random_out_rows = [ [r[0], r[1], "icons_random_" + Path(r[2]).name, r[3]] for r in random_out_rows ]
                writer.writerows(header_row + random_out_rows)

        fullres_paths = [f"fullres/{context}" for context in contextes.keys()]


        if index_path.exists():
            dest_index_path = dest_icons_path / "index.theme"
            if not dest_index_path.exists():
                self.make_index_theme(index_path, dest_index_path, fullres_paths, contextes)


        logging.info(f"You can run the Comfy workflow. csv files: {file_upto-1} todo: {len(out_rows)}")

        logging.info(f"Done – {ok} copied to outputs/make_icons_final, {failed} failed.")


    def make_icons(self, args):
        global draw_size
        global default_size


        # 4. Use the arguments in your code
        verbose : bool = args.verbose
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
            logging.debug("verbose")
        else:
            logging.basicConfig(level=logging.INFO)

        self.min_size = args.min_size
        if args.fullres_size > 0:
            default_size = self.fullres_size = args.fullres_size
        if args.draw_size > 0:
            draw_size = args.draw_size
            if self.fullres_size == 0 or self.fullres_size > draw_size:
                # don't rescale the final full res size larger than the drawing size
                self.fullres_size = draw_size

        if args.alt_output:
            self.alt_output_paths = args.alt_output

        if args.rows_per_file is not None:
            self.rows_per_file = int(args.rows_per_file)

        self.brightness = args.brightness
        if args.black:
            self.transparency_range = [ 32, 64 ]
            self.transparency_black = True
        elif args.white:
            self.transparency_range = [ 192, 223 ]
            self.transparency_black = False

        if args.transparency_range is not None:
            self.transparency_range = [ int(x) for x in args.transparency_range.split('-') ]

        icons_path = args.icons_path
        comfyui_path = args.comfyui_path
        self.main(icons_path, Path(comfyui_path))

if __name__ == "__main__":
    make_icons = MakeIcons()
    parser = argparse.ArgumentParser(description="Make gnome icons from a prompt.")

    # 2. Add arguments
    parser.add_argument("icons_path", help="Path where the icons are")  # Positional
    parser.add_argument("comfyui_path", help="ComfyUI path")  # Positional
    parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")  # Flag
    parser.add_argument("--transparency-range", type=str, default=None, help="Range for transparency, '32-64' default for black, '192-223' default for white")
    parser.add_argument("--black", action="store_true", help="default settings for black")
    parser.add_argument("--white", action="store_true", help="default settings for white")
    parser.add_argument("--brightness", type=float, default=1, help="0.5 darken by 50 percent. 1.5 brighten by 50 percent")
    parser.add_argument("--min-size", type=int, default=32, help="Do not convert images below this size. Set to zero to convert all.")
    parser.add_argument("--fullres-size", type=int, default=0, help="Fullres size")
    parser.add_argument("--draw-size", type=int, default=0, help="Draw size")
    parser.add_argument("-r", "--rows-per-file", help=f"rows per file. default {make_icons.rows_per_file}")
    parser.add_argument("--alt-output", nargs='+', type=str, help="Copy ComfyUI/output/make_icons to an alternative place and put it here.")

    # 3. Parse the command line inputs
    args = parser.parse_args()

    make_icons.make_icons(args)

