#!/usr/bin/env python3
"""
Recursively find all symlinks in source_folder and recreate them in dest_folder,
preserving the relative directory structure.
"""

import os
import sys
import argparse
# import shutil
import re
import logging
from pathlib import Path
import configparser
import hashlib




#########

CHUNK = 1 << 20  # 1 MiB read chunks


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def build_index(directory: Path) -> dict[str, Path]:
    """Return {sha256_hex: first_path} for every regular file under directory."""
    index: dict[str, Path] = {}
    skipped = 0

    for root, _, files in os.walk(directory):
        for name in files:
            path = Path(root) / name
            if not path.is_file() or path.is_symlink():
                skipped += 1
                continue
            try:
                digest = sha256(path)
            except OSError as e:
                logging.warn(f"  [WARN] cannot read {path}: {e}", file=sys.stderr)
                continue

            if digest not in index:
                index[digest] = path
                logging.info(f"  indexed {path}  ({digest[:12]}…)")
            else:
                logging.debug(f"  duplicate in dir1 ignored: {path}  (same as {index[digest]})")

    if skipped:
        logging.info(f"  skipped {skipped} symlink(s)/non-regular file(s) in dir1")

    return index


def deduplicate(directory: Path, index: dict[str, Path],
                dry_run: bool,) -> tuple[int, int]:
    """
    Walk directory 2.  For each regular file whose SHA is in index:
      - remove the file
      - create a symlink pointing to the dir1 counterpart.

    Returns (matched, errors).
    """
    matched = errors = 0

    for root, _, files in os.walk(directory):
        for name in files:
            root_short_folder = Path(root).relative_to(directory)
            if len(root_short_folder.parts) > 0 and str(root_short_folder.parts[0]) == "fullres":
                print(f"skip {root_short_folder}")
                continue
            path = Path(root) / name
            if not path.is_file() or path.is_symlink():
                continue
            try:
                digest = sha256(path)
            except OSError as e:
                logging.warn(f"  [WARN] cannot read {path}: {e}", file=sys.stderr)
                errors += 1
                continue

            if digest not in index:
                continue

            source = index[digest]          # file in dir1
            matched += 1

            logging.debug(f"  MATCH  {path}")
            source_rel = source.relative_to(path.parent, walk_up=True)
            logging.debug(f"    → {source_rel} {source}")

            if dry_run:
                logging.debug("    [dry-run] would remove and symlink")
                continue

            try:
                path.unlink()
                path.symlink_to(source_rel)
                logging.info("    done")
            except OSError as e:
                logging.error(f"    [ERROR] {e}", file=sys.stderr)
                errors += 1

    return matched, errors


def symlink_dupes(dir1, dir2, dry_run) -> None:

    dir1 = Path(dir1).resolve()
    dir2 = Path(dir2).resolve()

    for d, label in ((dir1, "dir1"), (dir2, "dir2")):
        if not d.is_dir():
            sys.exit(f"Error: {label} '{d}' is not a directory.")

    if dir2 == dir1 or str(dir2).startswith(str(dir1) + os.sep):
        sys.exit("Error: dir2 must not be the same as or inside dir1.")

    if dry_run:
        print("=== DRY RUN — no files will be modified ===\n")

    # --- Phase 1: index dir1 ---
    print(f"[1/2] Indexing '{dir1}' …")
    index = build_index(dir1)
    print(f"      {len(index)} unique file(s) indexed.\n")

    if not index:
        print("No files found in dir1. Nothing to do.")
        return

    # --- Phase 2: deduplicate dir2 ---
    print(f"[2/2] Scanning '{dir2}' for duplicates …")
    matched, errors = deduplicate(dir2, index, dry_run)

    print()
    print("=== Summary ===")
    print(f"  Unique files in dir1 : {len(index)}")
    print(f"  Files matched in dir2 : {matched}")
    print(f"  Errors               : {errors}")
    if dry_run:
        print("  (dry-run — nothing was changed)")

###########


def recreate_fullres_links(source_folder: Path, dest_folder: Path, dry_run: bool = False):
    dest_fullres_folder = dest_folder / "fullres"
    # Initialize the parser
    config = configparser.ConfigParser()

    # source_folder_absolute = source_folder.absolute()

    # Read the index.theme file
    config.read(source_folder / 'index.theme')

    context_paths = []
    context_paths_dict = {}

    # Example: Access the 'Icon Theme' section and the 'Name' key
    for path_str,path_info in config.items():
        if 'Context' in path_info:
            context = path_info['Context']
            context_paths.append([path_str, context, source_folder / Path(path_str)])
            context_paths_dict[path_str] = context


    symlinks_made = 0
    symlinks_no_target = 0
    for context_path_info in context_paths:
        # context_path = Path(context_path_info[0])
        context_full_path = context_path_info[2]

        # folder where to make the new link
        dest_context_path = dest_fullres_folder / Path(context_path_info[1])

        for root, dirs, files in os.walk(context_full_path, followlinks=False):
            for name in files:
                symlink_path = Path(root) / name
                if not symlink_path.is_symlink():
                    continue

                use_png = True

                link_target = Path(os.readlink(symlink_path))
                full_link_target = Path(os.path.abspath(str(symlink_path.parent / link_target)) )

                link_target_short_path = full_link_target.relative_to(source_folder.absolute())
                link_target_context = context_paths_dict.get(str(link_target_short_path.parent), None)
#                if link_target_context is None:
#                    # this is not in index.theme
#                    # Guess fullres path from path name.
#                    link_target_context = link_target_short_path.parent.name.capitalize()

                dest_link_target_icon_path = (dest_fullres_folder / Path(link_target_context) / link_target.name)

                dest_link_target_icon_path_png = dest_link_target_icon_path.with_suffix(".png")

                if dest_link_target_icon_path.is_symlink() or dest_link_target_icon_path.exists():
                    use_png = False
                elif dest_link_target_icon_path_png.is_symlink() or dest_link_target_icon_path_png.exists():
                    use_png = True
                else:
		            # should be made later when we try again
                    logging.debug(f"No fullres symlink destination: {dest_link_target_icon_path}")
                    symlinks_no_target += 1
                    continue

                dest_icon_path = (dest_context_path / name)
                if use_png:
                    dest_icon_path = dest_icon_path.with_suffix(".png")
                if dest_icon_path.is_symlink() or dest_icon_path.exists():
                    # already made the icon
                    # print(dest_icon_path)
                    continue

                if not full_link_target.exists():
                    logging.error(f"No target {full_link_target}")

                if use_png:
                    dest_link_target_icon_path = dest_link_target_icon_path.with_suffix(".png")

                link_to = dest_link_target_icon_path.relative_to(dest_context_path, walk_up=True)

                # find destination context
                logging.debug(f"make symlink: {dest_icon_path} -> {link_to}")

                symlinks_made += 1

                if not dry_run:
                    dest_icon_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_icon_path.symlink_to(link_to)

    logging.info(f"symlinks made: {symlinks_made}")
    return symlinks_made




def recreate_links(source_folder: Path, dest_folder: Path, dry_run: bool = False):
    source_folder = source_folder.resolve()
    dest_folder = dest_folder.resolve()

    if not source_folder.exists():
        print(f"Error: source folder does not exist: {source_folder}", file=sys.stderr)
        sys.exit(1)

    links_found = 0
    links_created = 0
    links_skipped = 0
    symlinks_no_target  = 0
    errors = []

    for root, dirs, files in os.walk(source_folder, followlinks=False):
        root_path = Path(root)

        # Check symlinks that appear as directories (os.walk won't recurse into them)
        entries = list(dirs) + list(files)

        for name in entries:
            source_entry_path = root_path / name

            if not source_entry_path.is_symlink():
                continue

            if re.search(r"\@\d+x", name) and source_entry_path.is_dir():
                # don't link dir, it could be a @x2 directory with a different resolution
                continue

            links_found += 1

            # Relative path from source root → used to mirror structure in dest
            rel_path = source_entry_path.relative_to(source_folder)
            dest_link_path = dest_folder / rel_path

            # The symlink target (may be relative or absolute)
            link_target = Path(os.readlink(source_entry_path))
            link_target_final = dest_link_path.parent / link_target
            link_target_final_png = link_target_final.with_suffix('.png')

            use_png = False
            if link_target_final.is_symlink() or link_target_final.exists():
                use_png = False
            elif link_target_final_png.is_symlink() or link_target_final_png.exists():
                use_png = True
            else:
	    	# This will be made in next loops
                logging.debug(f"No symlink destination: {link_target_final} source info:{source_entry_path}")
                links_skipped += 1
                symlinks_no_target += 1
                continue

            if source_entry_path.is_file(): # and dest_link_path.suffix == '.svg':
                if use_png:
                    dest_link_path = dest_link_path.with_suffix('.png')

            if dest_link_path.exists() or dest_link_path.is_symlink():
                logging.debug(f"Skip, done: {dest_link_path}")
                links_skipped += 1
                continue

            # link_source_final = source_entry_path.parent / link_target

            if not dest_link_path.exists():
                # symlink does not exist
#                if link_target.suffix not in ('.svg','.png'):
#                    link_target_final.parent.mkdir(parents=True, exist_ok=True)
#                    if link_source_final.is_file():
#                        shutil.copy(link_source_final, link_target_final)
#                else:
                if use_png:
                    link_target = link_target.with_suffix('.png')
                link_target_final = dest_link_path.parent / link_target
            else:
                print(f"4dox: {name}, {link_target_final} {dest_link_path}")
                logging.debug(f"Already done: {link_target_final}")
                links_skipped += 1
                continue

            logging.debug(f"Found: {name} {dest_link_path} -> {link_target}, from: {source_entry_path}")

            if dry_run:
                logging.info(f"[dry-run] Would create: {dest_link_path} -> {link_target}")
                links_created += 1
                continue


            # Create parent directories in dest if needed
            dest_link_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                os.symlink(link_target, dest_link_path)
                logging.debug(f"Created: {dest_link_path} -> {link_target}")
                links_created += 1
            except OSError as e:
                msg = f"Error creating {dest_link_path}: {e}"
                print(msg, file=sys.stderr)
                errors.append(msg)

    # Summary
    action = "Would create" if dry_run else "Created"
    print(f"\nDone. Found {links_found} link(s). {action}: {links_created}, Skipped: {links_skipped}, Errors: {len(errors)}")
    if errors:
        print("\nErrors encountered:")
        for e in errors:
            print(f"  {e}")
    return {
        "links_created" : links_created,
        "links_found" : links_found,
        "links_skipped" : links_skipped
    }

def copy_links(source_folder, dest_folder, dry_run=False):
    max_count = 8
    if dry_run:
        max_count = 1

    c = 0
    while c < max_count:
        r = recreate_links(source_folder, dest_folder, dry_run=dry_run)
        if r["links_created"] == 0:
            break
        c += 1

    c = 0
    while c < max_count:
        if recreate_fullres_links(source_folder, dest_folder, dry_run=dry_run) == 0:
            break
        c += 1

#    dest_folder = Path(args.dest_folder)
#    symlink_dupes(str(dest_folder / "fullres"), str(dest_folder), args.dry_run)

def main():
    parser = argparse.ArgumentParser(
        description="Recursively recreate symlinks from source_folder into dest_folder."
    )
    parser.add_argument("source_folder", type=Path, help="Folder to scan for symlinks")
    parser.add_argument("dest_folder", type=Path, help="Folder to recreate symlinks in")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print each link as it's processed")
    args = parser.parse_args()


    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)


    copy_links(args.source_folder, args.dest_folder, args.dry_run)


if __name__ == "__main__":
    main()
