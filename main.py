from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory
from werkzeug.utils import secure_filename
from google.cloud import language_v2
import os
from google.cloud import speech
from google.protobuf import wrappers_pb2
from google.cloud import texttospeech_v1

client_sr=speech.SpeechClient()
client_tr = texttospeech_v1.TextToSpeechClient()
client_nl = language_v2.LanguageServiceClient()
app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav','txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files():
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if allowed_file(filename):
            files.append(filename)
            print(filename)
    files.sort(reverse=True)
    return files

@app.route('/')
def index():
    files = get_files()
    text_contents = {}

    # Read the contents of the text files
    for file in files:
        if file.endswith('.txt'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
            try:
                with open(file_path, 'r') as f:
                    text_contents[file] = f.read()
            except Exception as e:
                print(f"Error reading file {file}: {e}")
                text_contents[file] = "Error reading file"

    return render_template('index.html', files=files, text_contents=text_contents)



def sample_recognize(content):
  audio=speech.RecognitionAudio(content=content)

  config=speech.RecognitionConfig(
  # encoding=speech.RecognitionConfig.AudioEncoding.MP3,
  # sample_rate_hertz=24000,
  language_code="en-US",
  model="latest_long",
  audio_channel_count=1,
  enable_word_confidence=True,
  enable_word_time_offsets=True,
  )

  operation=client_sr.long_running_recognize(config=config, audio=audio)

  response=operation.result(timeout=90)

  txt = ''
  for result in response.results:
    txt = txt + result.alternatives[0].transcript + '\n'

  return txt

def sample_synthesize_speech(text=None, ssml=None):
    input = texttospeech_v1.SynthesisInput()
    if ssml:
      input.ssml = ssml
    else:
      input.text = text

    voice = texttospeech_v1.VoiceSelectionParams()
    voice.language_code = "en-UK"
    # voice.ssml_gender = "MALE"

    audio_config = texttospeech_v1.AudioConfig()
    audio_config.audio_encoding = "LINEAR16"

    request = texttospeech_v1.SynthesizeSpeechRequest(
        input=input,
        voice=voice,
        audio_config=audio_config,
    )

    response = client_tr.synthesize_speech(request=request)

    return response.audio_content


def sample_analyze_sentiment(text_content):
    """
    Analyzes Sentiment in a string.

    Args:
      text_content: The text content to analyze.
    """
    client = client_nl  # Using your existing client_nl

    document_type_in_plain_text = language_v2.Document.Type.PLAIN_TEXT
    language_code = "en"
    document = {
        "content": text_content,
        "type_": document_type_in_plain_text,
        "language_code": language_code,
    }
    encoding_type = language_v2.EncodingType.UTF8

    response = client.analyze_sentiment(
        request={"document": document, "encoding_type": encoding_type}
    )

    # Calculate sentiment score
    score = response.document_sentiment.score * response.document_sentiment.magnitude
    if score > 0.75:
        sentiment = "POSITIVE"
    elif score < -0.75:
        sentiment = "NEGATIVE"
    else:
        sentiment = "NEUTRAL"

    result = {
        "score": response.document_sentiment.score,
        "magnitude": response.document_sentiment.magnitude,
        "sentiment": sentiment
    }

    print(f"Sentiment Analysis Result: {result}")
    return result


@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        print('No audio data')
        return redirect(request.url)

    file = request.files['audio_data']
    if file.filename == '':
        print('No selected file')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        filename = secure_filename(datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav')
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        with open(file_path, 'rb') as f:
            data = f.read()

        text = sample_recognize(data)
        print(text)

        # Perform sentiment analysis on the transcribed text
        sentiment_result = sample_analyze_sentiment(text)
        sentiment_text = (
            f"\nSentiment Analysis:\n"
            f"Score: {sentiment_result['score']}\n"
            f"Magnitude: {sentiment_result['magnitude']}\n"
            f"Overall Sentiment: {sentiment_result['sentiment']}\n"
        )

        # Save transcription and sentiment result in the same file
        text_filename = file_path + '.txt'
        with open(text_filename, 'w') as f:
            f.write(text)
            f.write(sentiment_text)

        print('File successfully uploaded, transcribed, and analyzed')
    else:
        print('Invalid file type')

    return redirect(url_for('index'))


@app.route('/upload/<filename>')
def get_file(filename):
    return send_file(filename)

    
@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form.get('text', '')
    if text:
        wav = sample_synthesize_speech(text)
        if wav:
            filename = 'tr_' + datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(file_path, 'wb') as f:
                f.write(wav)

            # Perform sentiment analysis on the input text
            sentiment_result = sample_analyze_sentiment(text)
            sentiment_text = (
                f"\nSentiment Analysis:\n"
                f"Score: {sentiment_result['score']}\n"
                f"Magnitude: {sentiment_result['magnitude']}\n"
                f"Overall Sentiment: {sentiment_result['sentiment']}\n"
            )

            # Save text input and sentiment result in the same file
            text_filename = file_path + '.txt'
            with open(text_filename, 'w') as f:
                f.write(text)
                f.write(sentiment_text)

            print('Text successfully converted to speech and analyzed')
        else:
            print('TTS Conversion Failed')
    else:
        print('No text provided')

    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)