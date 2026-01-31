import os
import requests

def download_file(url, dest_path):
    print(f"Downloading {url} to {dest_path}...")
    try:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download complete.")
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

base_url = "https://cdnjs.cloudflare.com/ajax/libs/photoswipe/5.4.4"
files = [
    f"{base_url}/photoswipe.css",
    f"{base_url}/umd/photoswipe.umd.min.js",
    f"{base_url}/umd/photoswipe-lightbox.umd.min.js"
]

target_dir = r"d:\PicSee\resources\photoswipe"

for url in files:
    filename = url.split("/")[-1]
    dest = os.path.join(target_dir, filename)
    download_file(url, dest)
