import requests
import zipfile
import json
import os
import shutil
from io import BytesIO

# Get the directory of the script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# URL of the repository ZIP file
REPO_URL = "https://github.com/Lucaslhm/Flipper-IRDB/archive/refs/heads/main.zip"

def download_and_extract_repo():
    print("Downloading repository...")
    response = requests.get(REPO_URL)
    if response.status_code != 200:
        raise Exception(f"Failed to download repository: Status code {response.status_code}")
    
    print("Extracting files...")
    with zipfile.ZipFile(BytesIO(response.content)) as zip_ref:
        zip_ref.extractall(SCRIPT_DIR)
    
    # The extracted folder name
    return os.path.join(SCRIPT_DIR, "Flipper-IRDB-main")

def parse_directory(path, depth=0):
    data = {'name': os.path.basename(path), 'children': []}
    
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path):
            child_data = parse_directory(item_path, depth + 1)
            if child_data['children']:  # Only add non-empty directories
                data['children'].append(child_data)
        elif item.endswith('.ir'):
            brand, model = extract_brand_and_model(item)
            file_data = {
                'name': item,
                'size': os.path.getsize(item_path),
                'brand': brand,
                'model': model
            }
            if depth == 1:  # Device Type level
                file_data['device_type'] = data['name']
            elif depth == 2:  # Brand level
                file_data['device_type'] = os.path.basename(os.path.dirname(path))
                file_data['brand'] = data['name']
            data['children'].append(file_data)
    
    return data

def extract_brand_and_model(filename):
    name_without_ext = os.path.splitext(filename)[0]
    parts = name_without_ext.split('_', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    else:
        return name_without_ext, ""

def count_files_by_category(data):
    counts = {
        'total': 0,
        'by_device_type': {},
        'by_brand': {}
    }

    def count_recursive(node):
        if 'device_type' in node:
            counts['total'] += 1
            device_type = node['device_type']
            brand = node['brand']
            counts['by_device_type'][device_type] = counts['by_device_type'].get(device_type, 0) + 1
            counts['by_brand'][brand] = counts['by_brand'].get(brand, 0) + 1
        else:
            for child in node.get('children', []):
                count_recursive(child)

    count_recursive(data)
    return counts

def main():
    try:
        repo_path = download_and_extract_repo()
        print("Parsing directory structure...")
        data = parse_directory(repo_path)
        
        output_path = os.path.join(SCRIPT_DIR, 'irdb_data.json')
        with open(output_path, 'w') as f:
            json.dump(data, f)
        
        print(f"Data saved to: {output_path}")

        # Generate and save statistics
        stats = count_files_by_category(data)
        stats_path = os.path.join(SCRIPT_DIR, 'irdb_stats.json')
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)
        
        print(f"Statistics saved to: {stats_path}")
        print(f"Total IR files: {stats['total']}")
        print(f"Device types: {len(stats['by_device_type'])}")
        print(f"Brands: {len(stats['by_brand'])}")
        
        # Clean up: remove the extracted folder
        shutil.rmtree(repo_path)
        print("Cleaned up temporary files.")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()