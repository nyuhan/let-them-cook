import json
from collections import defaultdict

with open("static/cuisine_mapping.json") as f:
    cuisine_mapping = json.load(f)

reverse = defaultdict(list)
for place_type, cuisine in cuisine_mapping.items():
    key = cuisine if cuisine is not None else "null"
    reverse[key].append(place_type)

# Sort keys and lists for consistency
output = {cuisine: sorted(types) for cuisine, types in sorted(reverse.items())}

with open("static/correct_reverse_mapping.json", "w") as f:
    json.dump(output, f, indent=2)

print("Saved static/correct_reverse_mapping.json")
