import json
from pathlib import Path


# Find our project folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Original dataset
INPUT_FILE = BASE_DIR / "data" / "email.json"

# Taxonomy we want to create
OUTPUT_FILE = BASE_DIR / "data" / "taxonomy_v1.json"


# Open email.json
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)


# This will store unique topic + subtopic combinations
taxonomy = set()


# Go through every email record
for record in data:

    topic = record.get("dominant_topic")
    subtopics = record.get("subtopics")

    if topic and subtopics:
        taxonomy.add((topic, subtopics))


# Convert the set into a list
taxonomy_list = []

for topic, subtopics in sorted(taxonomy):

    taxonomy_list.append({
        "dominant_topic": topic,
        "subtopics": subtopics
    })


# Create the final taxonomy object
result = {
    "taxonomy_version": "v1",
    "pairs": taxonomy_list
}


# Save it as JSON
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

    json.dump(
        result,
        f,
        indent=2,
        ensure_ascii=False
    )

print("Taxonomy created successfully!")
print("Total number of rows:", len(data))
print("Number of unique pairs:", len(taxonomy_list))
print("Saved to:", OUTPUT_FILE)