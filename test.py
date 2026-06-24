from flask import Flask, request, jsonify
import json
from datetime import datetime

app = Flask(__name__)

@app.route("/", methods=["POST"])
def receive_data():
    try:
        data = request.get_json(force=True)

        print("\n" + "=" * 80)
        print("REQUEST RECEIVED")
        print("=" * 80)

        payload_copy = dict(data)

        if "fingerprint_image" in payload_copy:
            payload_copy["fingerprint_image"] = (
                f"<BASE64 IMAGE DATA - LENGTH {len(payload_copy['fingerprint_image'])}>"
            )

        print(json.dumps(payload_copy, indent=4))

        with open("received_payload.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        print("\nField Summary")
        print("-" * 40)

        print("sensor_sn:", data.get("sensor_sn"))
        print("model:", data.get("model"))
        print("image_name:", data.get("image_name"))
        print("image_format:", data.get("image_format"))

        image_data = data.get("fingerprint_image")

        if image_data:
            print("fingerprint_image length:", len(image_data))
            print("fingerprint_image first 100 chars:")
            print(image_data[:100])
        else:
            print("fingerprint_image: NOT PRESENT")

        print("=" * 80)

        return jsonify({
            "status": "success",
            "message": "Payload received"
        }), 200

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)