import os
import sys
import subprocess
import importlib.util
import traceback
import time
import gc
import re
import json

def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def ensure_package(package):
    if importlib.util.find_spec(package) is None:
        print(f"{package} not found. Installing...")
        install_package(package)

# Ensure required packages are installed
ensure_package("tqdm")

import difflib
import argparse
from tqdm import tqdm
import logging

# Set up logging
logging.basicConfig(filename='ir_comparison_debug.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def read_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
            return file.read().splitlines()
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {str(e)}")
        return None

def write_file(file_path, content):
    try:
        with open(file_path, 'w', encoding='utf-8', newline='\n') as file:
            file.write('\n'.join(content))
        return True
    except Exception as e:
        logging.error(f"Error writing file {file_path}: {str(e)}")
        return False

def normalize_button_names(all_signals, mapping, file_path):
    # Normalize file_path to use forward slashes
    file_path = file_path.replace('\\', '/')

    # Load group patterns
    name_check = mapping.get('name-check', {})
    groups = name_check.get('$groups', {})
    # Build compiled regex patterns for groups
    group_patterns = {}
    for group_name, patterns in groups.items():
        compiled_patterns = []
        for pattern in patterns:
            if pattern.startswith('/') and pattern.endswith('/'):
                regex = pattern[1:-1]
                compiled_patterns.append(re.compile(regex, re.IGNORECASE))
            else:
                # Exact match
                compiled_patterns.append(pattern.lower())
        group_patterns[group_name] = compiled_patterns

    # Build mapping for the file category
    category_mappings = {}
    for category_pattern, buttons in name_check.items():
        if category_pattern.startswith('$'):
            continue  # Skip special keys

        # Handle multiple categories separated by commas
        category_patterns = category_pattern.split(',')
        for cat_pattern in category_patterns:
            cat_pattern = cat_pattern.strip()
            # Convert wildcard pattern to regex
            cat_regex = cat_pattern.replace('*', '.*')
            cat_regex = f"^{cat_regex}$"
            category_matcher = re.compile(cat_regex, re.IGNORECASE)
            if category_matcher.match(file_path):
                logging.debug(f"File '{file_path}' matches category pattern '{cat_pattern}'")
                # Found matching category, merge buttons
                for standard_name, patterns in buttons.items():
                    compiled_patterns = []
                    for pattern in patterns:
                        if pattern.startswith('$group:'):
                            group_name = pattern[len('$group:'):]
                            compiled_patterns.extend(group_patterns.get(group_name, []))
                        elif pattern.startswith('/') and pattern.endswith('/'):
                            regex = pattern[1:-1]
                            compiled_patterns.append(re.compile(regex, re.IGNORECASE))
                        else:
                            compiled_patterns.append(pattern.lower())
                    if standard_name in category_mappings:
                        category_mappings[standard_name].extend(compiled_patterns)
                    else:
                        category_mappings[standard_name] = compiled_patterns

    buttons_renamed = 0  # Counter for buttons renamed

    # Normalize button names
    for entry in all_signals:
        original_name = entry['name'].strip()
        new_name = original_name  # Default to original name
        for standard_name, patterns in category_mappings.items():
            for pattern in patterns:
                if isinstance(pattern, re.Pattern):
                    if pattern.match(original_name):
                        new_name = standard_name
                        break
                else:
                    # Exact match
                    if original_name.lower() == pattern.strip():
                        new_name = standard_name
                        break
            if new_name != original_name:
                logging.debug(f"Renaming button '{original_name}' to '{new_name}'")
                buttons_renamed += 1
                break  # Found a matching standard name
        # Update the name in the signal
        entry['name'] = new_name.strip()
        entry['signal'][0] = f'name: {entry["name"]}'
    return buttons_renamed

def clean_and_deduplicate(original_content, decoded_content, normalize=False, mapping=None, file_path=''):
    # Extract initial content (headers and initial comments) from original_content
    initial_content = []
    for line in original_content:
        if line.strip().startswith('#') or line.strip().startswith('Filetype:') or line.strip().startswith('Version:'):
            initial_content.append(line)
        else:
            break

    # Ensure initial_content ends with a single '#'
    while initial_content and initial_content[-1].strip() == '#':
        initial_content.pop()
    if initial_content and initial_content[-1].strip() != '#':
        initial_content.append('#')

    # Remove headers from decoded_content
    decoded_content_no_headers = []
    skip_headers = True
    for line in decoded_content:
        if skip_headers:
            if line.strip().startswith('#') or line.strip().startswith('Filetype:') or line.strip().startswith('Version:'):
                continue  # Skip header lines
            else:
                skip_headers = False
                decoded_content_no_headers.append(line)
        else:
            decoded_content_no_headers.append(line)

    # Process content to collect signals, keeping track of source and names
    all_signals = []
    # Process decoded_content first to prefer decoded signals
    for content, source in [
        (decoded_content_no_headers, 'decoded'),
        (original_content[len(initial_content):], 'original')
    ]:
        current_signal = []
        current_comments = []
        current_signal_name = ''
        for line in content + ['#']:  # Add '#' to ensure the last signal is processed
            line = line.rstrip('\n')
            name_match = re.match(r'^name\s*:\s*(.*)$', line.strip(), re.IGNORECASE)
            if name_match:
                # Start of a new signal
                if current_signal and current_signal_name:
                    # Append the previous signal to all_signals
                    name_value = current_signal_name.strip()
                    all_signals.append({
                        'name': name_value,
                        'comments': current_comments.copy(),
                        'signal': current_signal.copy(),
                        'source': source
                    })
                    current_signal.clear()
                    current_comments.clear()
                current_signal.append(line)
                current_signal_name = name_match.group(1).strip()
            elif line.strip().startswith('#'):
                # Comment line
                if current_signal and current_signal_name:
                    # Append the previous signal before the comment
                    name_value = current_signal_name.strip()
                    all_signals.append({
                        'name': name_value,
                        'comments': current_comments.copy(),
                        'signal': current_signal.copy(),
                        'source': source
                    })
                    current_signal.clear()
                    current_signal_name = ''
                current_comments.append(line)
            elif line.strip() == '':
                # Skip empty lines
                continue
            else:
                current_signal.append(line)
        if current_signal and current_signal_name:
            # Append the last signal
            name_value = current_signal_name.strip()
            all_signals.append({
                'name': name_value,
                'comments': current_comments.copy(),
                'signal': current_signal.copy(),
                'source': source
            })

    # Normalize button names if requested
    if normalize and mapping:
        buttons_renamed = normalize_button_names(all_signals, mapping, file_path)
    else:
        buttons_renamed = 0

    # Deduplicate signals based on 'name', preferring decoded signals
    unique_signals = {}
    duplicates_removed = 0
    for entry in all_signals:
        name = entry['name']
        source = entry['source']
        if name not in unique_signals:
            unique_signals[name] = entry
        else:
            existing_entry = unique_signals[name]
            if existing_entry['source'] == 'original' and source == 'decoded':
                # Replace original signal with decoded one
                unique_signals[name] = entry
                duplicates_removed += 1
            else:
                # Duplicate found, increment counter
                duplicates_removed += 1

    # Rebuild the cleaned content
    cleaned_content = initial_content.copy()
    comments_readded = 0
    for entry in unique_signals.values():
        comments = entry['comments']
        signal = entry['signal']
        # Add comments if present
        if comments and (not cleaned_content or cleaned_content[-1].strip() != '#'):
            cleaned_content.extend(comments)
            comments_readded += len(comments)
        # Add signal
        cleaned_content.extend(signal)
        # Ensure there's a '#' between signals for proper formatting
        if cleaned_content and cleaned_content[-1].strip() != '#':
            cleaned_content.append('#')

    # Remove any empty lines or extra '#' at the end of the file
    while cleaned_content and cleaned_content[-1].strip() in ('', '#'):
        cleaned_content.pop()

    # Normalize cleaned content to avoid multiple '#' lines
    normalized_cleaned_content = []
    prev_line_was_hash = False
    for line in cleaned_content:
        if line.strip() == '#':
            if not prev_line_was_hash:
                normalized_cleaned_content.append('#')
            prev_line_was_hash = True
        else:
            normalized_cleaned_content.append(line)
            prev_line_was_hash = False
    cleaned_content = normalized_cleaned_content

    return cleaned_content, duplicates_removed, buttons_renamed, comments_readded

def compare_files(original_file, decoded_file, normalize=False, mapping=None, relative_path=''):
    try:
        original_content = read_file(original_file)
        decoded_content = read_file(decoded_file)

        if original_content is None or decoded_content is None:
            return None

        # Clean and deduplicate the decoded content
        cleaned_content, duplicates_removed, buttons_renamed, comments_readded = clean_and_deduplicate(
            original_content,
            decoded_content,
            normalize,
            mapping,
            relative_path  # Pass the relative path to determine category
        )

        # Write the cleaned content back to the decoded file
        if not write_file(decoded_file, cleaned_content):
            logging.error(f"Failed to write cleaned content to {decoded_file}")
            return None

        # Compare original content with cleaned content
        differ = difflib.Differ()
        diff = list(differ.compare(original_content, cleaned_content))

        # Calculate difference ratio
        similarity = difflib.SequenceMatcher(None, '\n'.join(original_content), '\n'.join(cleaned_content)).ratio()
        difference_ratio = 1 - similarity

        # Check for lost comments
        original_comments = [line for line in original_content if line.strip().startswith('#')]
        cleaned_comments = [line for line in cleaned_content if line.strip().startswith('#')]
        lost_comments = [comment for comment in original_comments if comment not in cleaned_comments]

        return {
            'difference_ratio': difference_ratio,
            'lost_comments': len(lost_comments),
            'duplicates_removed': duplicates_removed,
            'buttons_renamed': buttons_renamed,
            'comments_readded': comments_readded,
            'diff_summary': summarize_diff(diff)
        }
    except Exception as e:
        logging.error(f"Error comparing files {original_file} and {decoded_file}: {str(e)}")
        logging.error(traceback.format_exc())
        return None

def summarize_diff(diff):
    added = sum(1 for line in diff if line.startswith('+ '))
    removed = sum(1 for line in diff if line.startswith('- '))
    changed = sum(1 for line in diff if line.startswith('? '))
    return f"Added: {added}, Removed: {removed}, Changed: {changed}"

def analyze_directories(original_dir, decoded_dir, threshold=0.1, file_limit=None, normalize=False, mapping=None):
    results = []
    skipped_files = []
    processed_files = 0
    total_duplicates_removed = 0
    total_lost_comments = 0
    total_difference_ratio = 0
    total_files_with_differences = 0
    total_buttons_renamed = 0
    total_comments_readded = 0

    # Get total number of .ir files for progress bar
    total_files = sum(1 for root, _, files in os.walk(original_dir) for file in files if file.endswith('.ir'))

    with tqdm(total=total_files, desc="Analyzing files", unit="file") as pbar:
        for root, _, files in os.walk(original_dir):
            for file in files:
                if file.endswith('.ir'):
                    try:
                        original_file = os.path.join(root, file)
                        relative_path = os.path.relpath(original_file, original_dir)
                        decoded_file = os.path.join(decoded_dir, relative_path)

                        logging.debug(f"Processing file: {relative_path}")

                        if os.path.exists(decoded_file):
                            comparison = compare_files(original_file, decoded_file, normalize, mapping, relative_path)
                            if comparison is not None:
                                total_duplicates_removed += comparison['duplicates_removed']
                                total_lost_comments += comparison['lost_comments']
                                total_difference_ratio += comparison['difference_ratio']
                                total_buttons_renamed += comparison['buttons_renamed']
                                total_comments_readded += comparison['comments_readded']
                                processed_files += 1

                                if comparison['difference_ratio'] > threshold or comparison['lost_comments']:
                                    results.append({
                                        'file': relative_path,
                                        'difference_ratio': comparison['difference_ratio'],
                                        'lost_comments': comparison['lost_comments'],
                                        'duplicates_removed': comparison['duplicates_removed'],
                                        'buttons_renamed': comparison['buttons_renamed'],
                                        'comments_readded': comparison['comments_readded'],
                                        'diff_summary': comparison['diff_summary']
                                    })
                                    total_files_with_differences += 1
                        else:
                            skipped_files.append(relative_path)

                        pbar.update(1)

                        if file_limit and processed_files >= file_limit:
                            logging.info(f"Reached file limit of {file_limit}. Stopping analysis.")
                            return results, skipped_files, {
                                'total_files_processed': processed_files,
                                'total_duplicates_removed': total_duplicates_removed,
                                'total_lost_comments': total_lost_comments,
                                'total_difference_ratio': total_difference_ratio,
                                'total_files_with_differences': total_files_with_differences,
                                'total_buttons_renamed': total_buttons_renamed,
                                'total_comments_readded': total_comments_readded
                            }

                        # Force garbage collection every 1000 files
                        if processed_files % 1000 == 0:
                            gc.collect()

                    except Exception as e:
                        logging.error(f"Error processing file {file}: {str(e)}")
                        logging.error(traceback.format_exc())
                        skipped_files.append(relative_path)
                        pbar.update(1)

    return results, skipped_files, {
        'total_files_processed': processed_files,
        'total_duplicates_removed': total_duplicates_removed,
        'total_lost_comments': total_lost_comments,
        'total_difference_ratio': total_difference_ratio,
        'total_files_with_differences': total_files_with_differences,
        'total_buttons_renamed': total_buttons_renamed,
        'total_comments_readded': total_comments_readded
    }

def load_mapping():
    mapping_json = '''
    {
        "name-check": {
            "$path-prefix": "",
            "$groups": {
                "power-toggle": [
                    "/^((power|pwr)[_\\\\s]*)?(toggle)?$/",
                    "/^((power|pwr)[_\\\\/\\\\s]*)?((on[_\\\\/\\\\s]*off)|(off[_\\\\/\\\\s]*on)|toggle)$/",
                    "/^(turn[_\\\\s]*)?((on[_\\\\/\\\\s]*off)|(off[_\\\\/\\\\s]*on))$/"
                ],
                "power-off": [
                    "/^((power|pwr)[_\\\\s]*)?off$/",
                    "/^(turn[_\\\\s]*)?(off)$/"
                ],
                "power-on": [
                    "/^((power|pwr)[_\\\\s]*)?on$/",
                    "/^(turn[_\\\\s]*)?(on)$/"
                ],
                "vol_up": [
                    "/^vol(ume)?[_\\\\s]*(up|[\\\\^+])$/"
                ],
                "vol_dn": [
                    "/^vol(ume)?[_\\\\s]*(d(o?w)?n|[v\\\\-])$/"
                ],
                "ch_next": [
                    "/^ch(an(nel)?)?[_\\\\s]*(up|[\\\\^+])$/"
                ],
                "ch_prev": [
                    "/^ch(an(nel)?)?[_\\\\s]*(d(o?w)?n|[\\\\v-])$/"
                ],
                "mute": [
                    "mute",
                    "mte",
                    "/^mute.*$/"
                ]
            },
            "TVs/*": {
                "Power": [
                    "$group:power-toggle"
                ],
                "Off": [
                    "$group:power-off"
                ],
                "Power_on": [
                    "$group:power-on"
                ],
                "Vol_up": [
                    "$group:vol_up"
                ],
                "Vol_dn": [
                    "$group:vol_dn"
                ],
                "Ch_next": [
                    "$group:ch_next"
                ],
                "Ch_prev": [
                    "$group:ch_prev"
                ],
                "Mute": [
                    "$group:mute"
                ]
            },
            "ACs/*": {
                "Off": [
                    "$group:power-off"
                ]
            },
            "Audio_Receivers/*,SoundBars/*,Speakers/*": {
                "Power": [
                    "$group:power-toggle"
                ],
                "Off": [
                    "$group:power-off"
                ],
                "Power_on": [
                    "$group:power-on"
                ],
                "Vol_up": [
                    "$group:vol_up"
                ],
                "Vol_dn": [
                    "$group:vol_dn"
                ],
                "Mute": [
                    "$group:mute"
                ]
            }
        }
    }
    '''
    return json.loads(mapping_json)

def main(original_dir, decoded_dir, threshold=0.1, output_file=None, file_limit=None, normalize=False):
    # Load mapping if normalization is enabled
    if normalize:
        mapping = load_mapping()
    else:
        mapping = None

    if not normalize and mapping is None:
        # Ask the user if they want to normalize buttons
        normalize_input = input("Do you want to normalize button names? (y/n): ").strip().lower()
        if normalize_input == 'y':
            normalize = True
            mapping = load_mapping()

    print("Starting analysis...")
    logging.info("Starting analysis...")

    start_time = time.time()
    results, skipped_files, totals = analyze_directories(original_dir, decoded_dir, threshold, file_limit, normalize, mapping)
    end_time = time.time()

    logging.info(f"Analysis completed in {end_time - start_time:.2f} seconds")

    # Calculate average difference ratio
    total_files_processed = totals['total_files_processed'] or 1
    average_difference = totals['total_difference_ratio'] / total_files_processed

    print("\nAnalysis Summary:")
    print(f"Total files processed: {totals['total_files_processed']}")
    print(f"Total files with significant differences: {totals['total_files_with_differences']}")
    print(f"Total duplicates removed: {totals['total_duplicates_removed']}")
    print(f"Total buttons renamed: {totals['total_buttons_renamed']}")
    print(f"Total comments re-added: {totals['total_comments_readded']}")
    print(f"Total lost comments: {totals['total_lost_comments']}")
    print(f"Average difference ratio: {average_difference:.2f}")
    print(f"Total time taken: {end_time - start_time:.2f} seconds")

    if results:
        print("\nFiles with significant differences:")
        header = f"{'File':<50} {'Diff Ratio':<12} {'Duplicates Removed':<18} {'Buttons Renamed':<16} {'Lost Comments':<14}"
        print(header)
        print('-' * len(header))
        for result in results[:10]:  # Print only the top 10 results
            print(f"{result['file']:<50} {result['difference_ratio']:<12.2f} {result['duplicates_removed']:<18} {result['buttons_renamed']:<16} {result['lost_comments']:<14}")
        if len(results) > 10:
            print(f"... and {len(results) - 10} more files")
    else:
        print("\nNo files with significant differences found.")

    if skipped_files:
        print(f"\nSkipped {len(skipped_files)} files (not found in decoded directory or error in processing)")
        if len(skipped_files) <= 10:
            print("List of skipped files:")
            for skipped in skipped_files:
                print(f" - {skipped}")
        else:
            print("List of first 10 skipped files:")
            for skipped in skipped_files[:10]:
                print(f" - {skipped}")
            print(f"... and {len(skipped_files) - 10} more skipped files")
    else:
        print("\nNo files were skipped.")

    if output_file:
        print(f"\nWriting summarized results to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as out_file:
            out_file.write("Analysis Summary:\n")
            out_file.write(f"Total files processed: {totals['total_files_processed']}\n")
            out_file.write(f"Total files with significant differences: {totals['total_files_with_differences']}\n")
            out_file.write(f"Total duplicates removed: {totals['total_duplicates_removed']}\n")
            out_file.write(f"Total buttons renamed: {totals['total_buttons_renamed']}\n")
            out_file.write(f"Total comments re-added: {totals['total_comments_readded']}\n")
            out_file.write(f"Total lost comments: {totals['total_lost_comments']}\n")
            out_file.write(f"Average difference ratio: {average_difference:.2f}\n")
            out_file.write(f"Total time taken: {end_time - start_time:.2f} seconds\n")

            out_file.write("\nFiles with significant differences:\n")
            if results:
                for result in results:
                    out_file.write(f"\nFile: {result['file']}\n")
                    out_file.write(f"Difference Ratio: {result['difference_ratio']:.2f}\n")
                    out_file.write(f"Duplicates Removed: {result['duplicates_removed']}\n")
                    out_file.write(f"Buttons Renamed: {result['buttons_renamed']}\n")
                    out_file.write(f"Comments Re-added: {result['comments_readded']}\n")
                    out_file.write(f"Lost Comments: {result['lost_comments']}\n")
                    out_file.write(f"Diff Summary: {result['diff_summary']}\n")
            else:
                out_file.write("No files with significant differences found.\n")

            out_file.write("\nSkipped files:\n")
            for skipped in skipped_files:
                out_file.write(f" - {skipped}\n")
        print(f"Summarized results written to {output_file}")

    logging.info("Analysis results written to output file")

if __name__ == "__main__":
    # Default values for IDE usage
    DEFAULT_ORIGINAL_DIR = r"Z:\scripts\ir files\Flipper-IRDB-main"
    DEFAULT_DECODED_DIR = r"Z:\scripts\ir files\DECODED-IRDB"
    DEFAULT_THRESHOLD = 0.1
    DEFAULT_OUTPUT_FILE = "ir_comparison_results.txt"
    DEFAULT_FILE_LIMIT = None  # Set to a number if you want to limit the files processed
    DEFAULT_NORMALIZE = False  # Set to True if you want to enable normalization by default

    # Check if script is run from command line
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Compare original and decoded IR files.")
        parser.add_argument("original_dir", help="Path to the original IRDB directory")
        parser.add_argument("decoded_dir", help="Path to the decoded IRDB directory")
        parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Difference ratio threshold (default: 0.1)")
        parser.add_argument("--output", help="Output file for detailed results")
        parser.add_argument("--file-limit", type=int, help="Limit the number of files to process")
        parser.add_argument("--normalize", action="store_true", help="Normalize button names")
        args = parser.parse_args()

        main(args.original_dir, args.decoded_dir, args.threshold, args.output, args.file_limit, args.normalize)
    else:
        # Running in IDE
        main(DEFAULT_ORIGINAL_DIR, DEFAULT_DECODED_DIR, DEFAULT_THRESHOLD, DEFAULT_OUTPUT_FILE, DEFAULT_FILE_LIMIT, DEFAULT_NORMALIZE)

print("\nAnalysis complete. Check 'ir_comparison_debug.log' for detailed logs.")
