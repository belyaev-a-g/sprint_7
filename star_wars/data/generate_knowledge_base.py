import os
import json
import re

ORIGINAL_DIR = "source"
OUTPUT_DIR = "knowledge_base"
TERMS_MAP_PATH = "terms_map.json"

# Create output data directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load terms map
with open(TERMS_MAP_PATH, 'r', encoding='utf-8') as f:
    terms_map = json.load(f)

# Gather all replacement pairs into flat array
replacement_pairs = []
for category in terms_map.values():
    for orig, repl in category.items():
        replacement_pairs.append((orig, repl))

# Sort by length to except wrong replacements like 'new original'
replacement_pairs.sort(key=lambda x: len(x[0]), reverse=True)

compiled_replacements = []
for orig, repl in replacement_pairs:
    pattern = re.escape(orig)
    # allow special symbols
    regex = re.compile(r'(?<!\w)' + pattern + r'(?!\w)', flags=re.IGNORECASE)
    compiled_replacements.append((regex, repl))

def apply_replacements(text):
    for regex, repl in compiled_replacements:
        def replace_func(match):
            matched_text = match.group(0)
            if matched_text[0].isupper():
                return repl[0].upper() + repl[1:] if len(repl) > 1 else repl.upper()
            else:
                return repl.lower()
        text = regex.sub(replace_func, text)
    return text

# Generate new files
for filename in os.listdir(ORIGINAL_DIR):
    if not filename.endswith('.txt'):
        continue

    input_path = os.path.join(ORIGINAL_DIR, filename)
    output_path = os.path.join(OUTPUT_DIR, filename)

    print(f"Processing {filename}...")

    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip metadata
    if content.startswith('# Source:') and '\n\n' in content:
        header_end = content.find('\n\n')
        header = content[:header_end]
        body = content[header_end + 2:]
    else:
        header = ""
        body = content

    # Apply replacements
    new_body = apply_replacements(body)

    new_content = (header + '\n\n' + new_body) if header else new_body

    # Save new file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"OK: {len(body)} characters saved")

print("\ndone\n")
