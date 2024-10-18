"""
This module provides functionalities for Optical Character Recognition (OCR).
"""

import subprocess
from pathlib import Path
from typing import List, Dict, Union
import pymupdf
from .utils import get_logger


logger = get_logger(__name__)

class OCR:
    """
    OCR class.
    This class provides functionalities for Optical Character Recognition (OCR) in a PDF file.
    """

    @staticmethod
    def _ocr_pdf(input_pdf: Union[str, Path], output_pdf: Union[str, Path], language='eng+spa') -> None:
        """
        Adds an OCR text layer to scanned PDF files, allowing them to be searched using OCRmyPDF.

        Args: 
            input_pdf (str, Path): The path to the input PDF file.
            output_pdf (str, Path): The path to the output PDF file.
            language (str): The language(s) to use for OCR. Default is 'eng+spa' (English and Spanish).
        
        Returns:
            None
        """

        try:
            # Construir el comando
            comando = [
                'ocrmypdf',
                '-l', language,
                '--force-ocr',
                '--jobs', '4',  # Número de trabajos en paralelo
                '--output-type', 'pdf',
                str(input_pdf),
                str(output_pdf)
            ]
            # Ejecutar el comando como proceso hijo
            subprocess.run(comando, check=True)
            logger.info("OCR applied successfully to %s", input_pdf)
        except subprocess.CalledProcessError as e:
            logger.error("Error applying OCR: %s", e)

    @classmethod
    def get_ocr(cls, file_path: str) -> List[Dict]:
        """
        Extracts text of each page from a PDF file using PyMuPDF.

        Args:
            file_path (str): The path to the PDF file.
        
        Returns:
            List[Dict]: A list of dictionaries containing the text and metadata of each page.
        """

        file = Path(file_path).resolve()
        cls._ocr_pdf(file, file)
        elements = []
        metadata = {
            'filetype': 'application/pdf',
            'filename': file.name,
            'page_number': 0
        }
        doc = pymupdf.open(file)  # Abrir el archivo PDF
        for page in doc:
            metadata_copy = metadata.copy()  # Crear una copia del diccionario
            metadata_copy['page_number'] = page.number + 1
            elements.append({
                'metadata': metadata_copy,
                # Obtener el texto de la página y codificarlo en UTF-8
                'text': page.get_text().encode('utf-8')
            })
        doc.close()
        logger.info("Text extracted from %s", file)
        return elements
    
    @staticmethod
    def get_dev_ocr(file_path: str) -> List[Dict]:
        """
        Extracts text from a plain text file, e.g. {'.txt', '.html', '.py'}.

        Args:
            file_path (str): The path to the text file.

        Returns:
            List[Dict]: A list of dictionaries containing the text and metadata of the file.
        """

        file = Path(file_path)
        metadata = {"filetype": f'text/{file.suffix[1:]}' , "filename": file.name}
        text = file.read_text(encoding='utf-8')
        data = {
            'metadata': metadata, 
            'text': text
        }
        logger.info("Text extracted from %s", file)
        return [data]
