
import re
import sys
import hashlib
from pathlib import Path

icons_path = sys.argv[1]
if not icons_path:
    print("specify the path to the mimetypes icons")
    exit(1)
icons_path = Path(icons_path)

# Get files in the current directory
# files = [f.name for f in (Path(icons_path) ).iterdir() if(f.is_file() and not f.is_symlink()) ]
files = [f.name for f in icons_path.iterdir() if(f.is_file()) ]
my_dict : dict = {}
# /home/hankin/.icons/Tela/scalable/mimetypes/
#with open("/tmp/telamime.txt", "r") as file:
for line in files:
    # Remove trailing newline characters and whitespace
    cleaned_line = line.strip()
    cleaned_line = Path(cleaned_line).stem
    
    # Skip empty lines to prevent splitting errors
    if cleaned_line:
        # Split by the separator (only at the first occurrence)
        
        # Save stripped versions into the dictionary
        my_dict[cleaned_line.strip()] = line


done_sha = {}
with open("/etc/mime.types", "r") as file:
    for line in file:
        # Remove trailing newline characters and whitespace
        cleaned_line = line.strip()
        if cleaned_line:
            arr = re.split(r"\s+", cleaned_line)
            if len(arr) >= 2:
                ok=False
                m = arr[0]

                if m in my_dict:
                    ok=True
                else:
                    m2 = m.replace('/','-')
                    if m2 in my_dict:
                        m = m2
                        ok=True
                    else:
                        m2 = m2.replace('+','_')
                        if m2 in my_dict:
                            m = m2
                            ok=True
                        else:
                            continue


                if ok:
                    # Open the file in read-binary mode
                    file_name = my_dict[m]
                    digest = hashlib.sha256((icons_path / file_name).read_bytes()).hexdigest()
                    if digest not in done_sha:
                        Path(f"t.{arr[1]}").write_bytes(b"1")
                        done_sha[digest] = True

