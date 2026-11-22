import csv
import json
import os

JSON_PATH = os.path.join(os.path.dirname(__file__), "campus_data.json")
CSV_PATH = os.path.join(os.path.dirname(__file__), "campus_data.csv")


def main() -> None:
    if not os.path.exists(JSON_PATH):
        raise FileNotFoundError(f"Missing JSON file: {JSON_PATH}")

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Expected campus_data.json to be a JSON object mapping intent -> answer")

    # Write CSV with headers: intent,answer
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["intent", "answer"])
        for intent, answer in data.items():
            writer.writerow([intent, answer])

    print(f"Converted {len(data)} rows to: {CSV_PATH}")


if __name__ == "__main__":
    main()
