import json
from collections import Counter

with open("data/hotpot_100_final_balanced.json", encoding="utf-8") as f:
    data = json.load(f)

print(Counter([x["difficulty"] for x in data]))