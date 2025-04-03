from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory
from werkzeug.utils import secure_filename
import os

# Google Cloud STT
from google.cloud import speech

# Gemini AI
import google.generativeai as genai

# Flask setup
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Allowed file check
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# List uploaded files
def get_files():
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if allowed_file(filename):
            files.append(filename)
    files.sort(reverse=True)
    return files

# Home page
@app.route('/')
def index():
    files = get_files()
    text_contents = {}
    for file in files:
        if file.endswith('.txt'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
            try:
                with open(file_path, 'r') as f:
                    text_contents[file] = f.read()
            except Exception as e:
                text_contents[file] = f"Error reading file: {e}"
    return render_template('index.html', files=files, text_contents=text_contents)

# STT
def transcribe_audio(file_path):
    client = speech.SpeechClient()
    with open(file_path, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        language_code="en-US",
        audio_channel_count=1,
        enable_word_confidence=True,
        enable_word_time_offsets=True,
        model="latest_long"
    )

    operation = client.long_running_recognize(config=config, audio=audio)
    response = operation.result(timeout=90)

    transcript = ''
    for result in response.results:
        transcript += result.alternatives[0].transcript + '\n'
    return transcript.strip()

# Gemini call with transcript
def generate(transcript, prompt):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

    model = genai.GenerativeModel("models/gemini-1.5-flash")  # Flash 2.0 alias
    full_prompt = f"{prompt}\n\nTranscript:\n{transcript}"
    response = model.generate_content(full_prompt)
    return response.text

# Upload route
@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        return redirect(request.url)

    file = request.files['audio_data']
    if file.filename == '':
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav')
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        transcript = transcribe_audio(file_path)

        prompt = (
            "Please provide an exact transcript for the audio, followed by sentiment analysis.\n\n"
            "Format:\n\n"
            "Text: [transcribed text]\n\n"
            "Sentiment Analysis: positive | neutral | negative"
        )

        result_text = generate(transcript, prompt)

        with open(file_path + '.txt', 'w') as f:
            f.write(result_text)

    return redirect(url_for('index'))

# File routes
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/upload/<filename>')
def get_file(filename):
    return send_file(filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

