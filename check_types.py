import json
from collections import defaultdict

with open("static/types.txt") as f:
    types = {line.strip() for line in f if line.strip()}

with open("static/cuisine_mapping.json") as f:
    cuisine_mapping = json.load(f)

with open("static/correct_reverse_mapping.json") as f:
    reverse_mapping = json.load(f)

# --- Check 1: types.txt vs cuisine_mapping.json keys ---
mapping_keys = set(cuisine_mapping.keys())

only_in_types = types - mapping_keys
only_in_mapping = mapping_keys - types

if only_in_types:
    print("In types.txt but NOT in cuisine_mapping.json:")
    for t in sorted(only_in_types):
        print(f"  {t}")

if only_in_mapping:
    print("In cuisine_mapping.json but NOT in types.txt:")
    for t in sorted(only_in_mapping):
        print(f"  {t}")

if not only_in_types and not only_in_mapping:
    print("types.txt <-> cuisine_mapping.json: all types match perfectly.")

# --- Check 2: correct_reverse_mapping.json is exact reverse of cuisine_mapping.json ---
print()

# Build expected reverse mapping from cuisine_mapping.json
expected_reverse = defaultdict(set)
for place_type, cuisine in cuisine_mapping.items():
    expected_reverse[cuisine].add(place_type)

expected_cuisines = set(expected_reverse.keys())
actual_cuisines = set(reverse_mapping.keys())

missing_cuisines = expected_cuisines - actual_cuisines
extra_cuisines = actual_cuisines - expected_cuisines

if missing_cuisines:
    print("Cuisines in cuisine_mapping.json but missing from reverse_cuisine_mapping.json:")
    for c in sorted(missing_cuisines):
        print(f"  {c}")

if extra_cuisines:
    print("Cuisines in reverse_cuisine_mapping.json but not in cuisine_mapping.json:")
    for c in sorted(extra_cuisines):
        print(f"  {c}")

# For cuisines present in both, compare the type sets
mismatch_found = False
for cuisine in sorted(expected_cuisines & actual_cuisines):
    expected_types = expected_reverse[cuisine]
    actual_types = set(reverse_mapping[cuisine])
    missing_types = expected_types - actual_types
    extra_types = actual_types - expected_types
    if missing_types or extra_types:
        mismatch_found = True
        print(f"Mismatch for cuisine '{cuisine}':")
        if missing_types:
            print(f"  Missing from reverse: {sorted(missing_types)}")
        if extra_types:
            print(f"  Extra in reverse:     {sorted(extra_types)}")

if not missing_cuisines and not extra_cuisines and not mismatch_found:
    print("reverse_cuisine_mapping.json is an exact reverse of cuisine_mapping.json.")
