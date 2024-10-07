import os
from typing import Optional, List, Dict
from werkzeug.utils import secure_filename
from flask import Flask, request
from core import FileManager, AcceptedFiles, Another, OCR, TextChunk, get_logger


UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'txt', 'rtf', 'html', 'java', 'py', 'c', 'cpp', 'js', 'pdf', 'png', 'jpg', 'jpeg', 'ppt', 'pptx', 'doc', 'docx'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def ensure_file_format(file: str) -> Optional[str]:
    file_manager = FileManager()

    if '.' in file and file.rsplit('.', 1)[1].lower() \
            in ['pdf', 'txt', 'rtf', 'html', 'java', 'py', 'c', 'cpp', 'js']:
        file_manager.set_strategy(AcceptedFiles())
    else:
        file_manager.set_strategy(Another())

    path = file_manager.execute_strategy(file, dst_dir='./uploads/documents/')
    return path


def make_ocr(file: str) -> List[Dict]:
    ocr = OCR()
    if file.lower().endswith('.pdf'):
        text = ocr.get_ocr(file)
    else:
        text= ocr.get_dev_ocr(file)
    return text


@app.get("/hello")
def hello():
    return "<h2>Hello, World!</h2>"


@app.post('/upload')
def upload_file():
    # check if the post request has the file part
    if 'file' not in request.files:
        return "<h2>No file sent</h2>"
    
    file = request.files['file']
    if file.filename == '':
        return "<h2>No file sent</h2>"
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        path_file = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path_file)
        accepted_file = ensure_file_format(path_file)
        text_file = make_ocr(accepted_file)
        return "<h2>File uploaded successfully</h2> <br> <h3>Text extracted:</h3> <br> <p>{}</p>".format(text_file)
    else:
        return "<h2>Invalid file format</h2>"


if __name__ == "__main__":
    app.run(debug=True)
