import json
# import sys
import urllib.request
from pathlib import Path
import urllib.parse
from datetime import datetime
import argparse


import time
import requests

base_url = "http://localhost:8188"
copy_only = False
workflow_api = "make_icons_workflow_copy_only_api.json" if copy_only else "make_icons_workflow_api.json" 

def poll_website(url, interval=30, max_retries=3):
    session = requests.Session()  # reuse TCP connection

    has_queue = False
    while True:
        queue_remaining = 0
        for attempt in range(max_retries):
            try:
                response = session.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                queue_remaining = data.get('exec_info', {}).get('queue_remaining')

                print(f"[{datetime.now():%H:%M:%S}] Got data: {data}")

                if queue_remaining is not None:
                    queue_remaining = int(queue_remaining)

                break  # success, exit retry loop

            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # exponential backoff: 1s, 2s, 4s
        if queue_remaining > 0:
            has_queue = True
        elif has_queue and queue_remaining == 0:
            break

        time.sleep(interval)


def run_csv(filename, prompt, seed):
    # Load your exported API JSON
    with open(workflow_api, "r", encoding="utf-8") as f:
        workflow_data = json.load(f)

    found = False
    seed_found = False
    for k,v in workflow_data.items():
        class_type = v.get("class_type")
        if class_type == "Spreadsheet2VideoLoadText":
            file = v.get("inputs",{}).get("text_file")
            if file is not None:
                v.get("inputs",{})["text_file"] = filename
                found = True
        elif class_type == "RandomNoise":
            v.get("inputs",{})["noise_seed"] = seed
            seed_found = True

    text_inputs = workflow_data.get("75:74", {}).get("inputs")
    if text_inputs:
        text_inputs["text"] = prompt
    else:
        found = False

    if not copy_only and (not found or not seed_found):
        raise Exception("bad workflow json, could not find text_file or seed")

    # Change parameters dynamically if needed (Optional)
    # Example: workflow_data["6"]["inputs"]["text"] = "A futuristic city skyline"

    # print(json.dumps(workflow_data))
    # Package the payload for ComfyUI's API
    payload = {"prompt": workflow_data}
    data = json.dumps(payload).encode('utf-8')


    # Send the execution request to the local server
    url = base_url + "/prompt"
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

    try:
        with urllib.request.urlopen(req) as response:
            print("Workflow successfully queued on startup!")
            json_str = response.read().decode("utf-8")
            json.loads(json_str)
            poll_website(url)
            return (True, workflow_data)
    except Exception as e:
        print(f"Failed to run workflow: {e}")
        return (False, workflow_data)

def wait_for_start():
    while True:
        url = base_url
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    time.sleep(30)  # wait a little just to be sure it's started
                    return True
        except Exception:
            pass
        time.sleep(30)
    return False

def reboot_comfy():
    try:
        url = base_url + "/api/manager/reboot"
        req = urllib.request.Request(url, headers={}, method="POST")
        with urllib.request.urlopen(req): # as response:
            # data = response.text
            pass

    except Exception as e:
        if not isinstance(e, ConnectionResetError):
            print(f"Reboot Error {e}")

    time.sleep(30)
    wait_for_start()


def run_comfy(args):
    comfy_path = Path(args.comfy_path)
    prompt = args.prompt
    seed = args.seed
    input_path = comfy_path / "input"
    for csv in input_path.glob("make_icons*.csv"):
        print(f"run {csv.name}")
        (_, workflow_data) = run_csv(csv.name, prompt, seed)

        workflow_path = comfy_path / "output/make_icons_final/prompt_workflow.json"
        workflow_path.write_text(json.dumps(workflow_data), encoding="utf-8")

        # wait for comfyui restart
        reboot_comfy()
        print(datetime.now().astimezone().isoformat())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ComfyUI to make gnome icons.")

    # 2. Add arguments
    parser.add_argument("comfy_path", help="ComfyUI path")  # Positional
    parser.add_argument("prompt", help="The prompt to use")  # Positional
    parser.add_argument("--seed", type=int, default=1, help="seed")  # Flag    
    # 3. Parse the command line inputs                                                                           
    args = parser.parse_args()            

    run_comfy(args)
