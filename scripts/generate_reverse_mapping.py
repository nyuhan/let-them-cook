import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(ROOT, "static/types.json")) as f:
    types_mapping = json.load(f)

reverse = defaultdict(list)
for type, mapped_type in types_mapping.items():
    key = mapped_type if mapped_type is not None else "null"
    reverse[key].append(type)

# Sort keys and lists for consistency
output = {key: sorted(values) for key, values in sorted(reverse.items())}

with open(os.path.join(ROOT, "static/types_reversed.json"), "w") as f:
    json.dump(output, f, indent=2)

print("Saved static/types_reversed.json")
