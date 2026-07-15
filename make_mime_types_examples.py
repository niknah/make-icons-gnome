
import re
import sys
from pathlib import Path

icons_path = sys.argv[1]
if not icons_path:
    print("specify the path to the mimetypes icons")
    exit(1)

# Get files in the current directory
files = [f.name for f in (Path(icons_path) ).iterdir() if(f.is_file() and not f.is_symlink()) ]
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
        my_dict[cleaned_line.strip()] = True

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
                        ok=True
                if ok:
                    Path(f"t.{arr[1]}").write_bytes("1")

