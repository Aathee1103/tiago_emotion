from flask import Flask, request, jsonify
import numpy as np
import cv2
from deepface import DeepFace
import threading

app = Flask(__name__)

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

latest_frame = None

#cv2.namedWindow("Live Emotion Feed", cv2.WINDOW_NORMAL)


def display_loop():
    global latest_frame

    while True:
        if latest_frame is not None:
            cv2.imshow("Live Emotion Feed", latest_frame)
            cv2.waitKey(1)


threading.Thread(target=display_loop, daemon=True).start()


@app.route("/emotion", methods=["POST"])
def emotion():

    global latest_frame

    file = request.files["image"]
    img_array = np.frombuffer(file.read(), np.uint8)
    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"error": "invalid image"}), 400

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    faces = face_cascade.detectMultiScale(gray, 1.1, 5)

    if len(faces) == 0:
        cv2.putText(frame, "No face detected", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    for (x, y, w, h) in faces:

        face_roi = rgb[y:y+h, x:x+w]

        try:
            result = DeepFace.analyze(
                face_roi,
                actions=['emotion'],
                enforce_detection=False
            )
            emotion = result[0]["dominant_emotion"]
        except:
            emotion = "error"

        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(frame, emotion, (x, y-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (0, 255, 0), 2)

    latest_frame = frame

    return jsonify({
        "faces": len(faces)
    })


if __name__ == "__main__":
    app.run(host="192.168.1.175", port=5000, debug=False)
