from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/race/1/upload", methods=["POST"])
def upload():
    print("Received request")

    if request.is_json:
        data = request.get_json()
        print("JSON Payload:", data)
    else:
        data = request.form.to_dict()
        print("Form data:", data)
        if request.files:
            for key, file in request.files.items():
                print(f"Received file: key='{key}', filename='{file.filename}', content_type='{file.content_type}'")

    return jsonify({'status': 'ok'}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)