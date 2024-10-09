import os
from typing import Optional, List, Dict
import json
import polars as pl
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify
from core import FileManager, AcceptedFiles, Another, OCR, TextChunk, MilvusManager


UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'txt', 'html', 'md', 'java', 'py', 'c', 'cpp', 'js', 'pdf', 'png', 'jpg', 'jpeg', 'ppt', 'pptx', 'doc', 'docx'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_file_format(file: str) -> Optional[str]:
    file_manager = FileManager()
    if '.' in file and file.rsplit('.', 1)[1].lower() \
            in ['pdf', 'txt', 'html', 'md', 'java', 'py', 'c', 'cpp', 'js']:
        file_manager.set_strategy(AcceptedFiles())
    else:
        file_manager.set_strategy(Another())
    path = file_manager.execute_strategy(file, dst_dir='./uploads/documents/')
    return path

def make_ocr(file: str) -> List[Dict]:
    if file is not None and file.lower().endswith('.pdf'):
        data = OCR.get_ocr(file)
    else:
        data = OCR.get_dev_ocr(file)
    return data

def get_text_chunks(ocr_text: List[Dict]) -> pl.DataFrame:
    text_chunk = TextChunk()
    df_text = text_chunk.add_chunks_to_dataframe(ocr_text)
    text_chunk.save_checkpoint('./data/checkpoint.db')
    return df_text

def insert_points(df_points: pl.DataFrame) -> None:
    milvus_manager = MilvusManager("collection")
    milvus_manager.create_collection()
    milvus_manager.insert_points(df_points)

def get_context(query: str):
    milvus_manager = MilvusManager("collection")
    data = milvus_manager.search_points(query)
    points = json.loads(data)
    context = []
    for point in points[0]:
        context.append(point['entity'])
    return context


@app.get("/hello")
def hello():
    return "<h1>Hello, World!</h1>"

@app.post('/upload')
def upload_file():
    # check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({"error": "No file has been sent: 'file'"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file has been sent: 'file'"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        path_file = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path_file)
        accepted_file = ensure_file_format(path_file)       # Ensure file format
        text_file = make_ocr(accepted_file)                 # Extract text from file (OCR)
        text_chunks = get_text_chunks(text_file)            # Get text chunks (pl.DataFrame)
        insert_points(text_chunks)                          # Insert points in Milvus
        return jsonify({"message": "File uploaded successfully"}), 200
    else:
        return jsonify({"error": "Invalid file format: 'file'"}), 400
    
@app.post('/search')
def search_similarity():
    text_query = request.args.get('text_query')
    if text_query is None:
        return jsonify({"error": "No query has been sent: 'text_query'"}), 400
    context = get_context(text_query)
    return jsonify({"context": context}), 200
    

if __name__ == "__main__":
    app.run(debug=True)
