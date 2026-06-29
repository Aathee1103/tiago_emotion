import cv2
from deepface import DeepFace

# Load face cascade classifier
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

# ✅ Use video file instead of webcam
cap = cv2.VideoCapture("/app/emotion_test.mp4")  # <-- put your mp4 path here

# Check if video opened correctly
if not cap.isOpened():
    print("ERROR: Cannot open video file")
    exit()

while True:

    # Capture frame-by-frame
    ret, frame = cap.read()

    # Stop if video ends
    if not ret or frame is None:
        print("End of video or failed to read frame")
        break

    # Convert frame to grayscale
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect faces
    faces = face_cascade.detectMultiScale(
        gray_frame,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30)
    )

    for (x, y, w, h) in faces:

        # Extract face ROI (use original color frame)
        face_roi = frame[y:y+h, x:x+w]

        try:
            # Emotion analysis
            result = DeepFace.analyze(
                face_roi,
                actions=['emotion'],
                enforce_detection=False
            )

            emotion = result[0]['dominant_emotion']

            # Draw rectangle + label
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
            cv2.putText(
                frame,
                emotion,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255),
                2
            )

        except Exception as e:
            print("DeepFace error:", e)

    # Show output
    cv2.imshow("Emotion Detection (Video)", frame)

    # Press 'q' to quit early
    if cv2.waitKey(25) & 0xFF == ord('q'):
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()