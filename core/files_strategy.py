import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import requests
from requests.exceptions import RequestException


class Strategy(ABC):
    @abstractmethod
    def execute(self, src_path: str, dst_path: Optional[str] = None, dst_dir: Optional[str] = None) -> Optional[str]:
        pass


class AcceptedFiles(Strategy):
    def execute(self, src_path: str, dst_path: Optional[str] = None, dst_dir: Optional[str] = None):
        if dst_path and dst_dir:
            print("Error: dst_path and dir_name cannot be used at the same time")
            return
        if dst_path:
            shutil.move(src_path, dst_path)
            return dst_path
        elif dst_dir:
            try:
                # Crear el directorio destino si no existe
                os.makedirs(os.path.dirname(dst_dir), exist_ok=True)

                # Mover el archivo
                output_path = shutil.move(src_path, dst_dir)
                return output_path
            except Exception as e:
                print("Error moving the file: ", e)


class Another(Strategy):
    def execute(self, src_path: str, dst_path: Optional[str] = None, dst_dir: Optional[str] = None):
        if dst_path and dst_dir:
            print("Error: dst_path and dir_name cannot be used at the same time")
            return

        libre_office_url = "http://localhost:2004/request"
        with open(src_path, 'rb') as file:
            files = {'file': file}
            data = {'convert-to': 'pdf'}

            try:
                response = requests.post(
                    url=libre_office_url, files=files, data=data, timeout=20)
                response.raise_for_status()
            except (RequestException, Exception) as e:
                print("Error converting the file: ", e)

        if dst_path:
            with open(dst_path, 'wb') as output_file:
                output_file.write(response.content)
            print("Archivo convertido exitosamente y guardado en: ", dst_path)
            return dst_path
        elif dst_dir:
            os.makedirs(os.path.dirname(dst_dir), exist_ok=True)
            output_path = dst_dir + Path(src_path).stem + '.pdf'
            with open(output_path, 'wb') as output_file:
                output_file.write(response.content)
            print("Archivo convertido exitosamente y guardado en: ", output_path)
            return output_path


class FileManager:
    def __init__(self):
        self._strategy = None

    def set_strategy(self, strategy: Strategy):
        self._strategy = strategy

    def execute_strategy(self, src_path: str, dst_path: Optional[str] = None, dst_dir: Optional[str] = None) -> Optional[str]:
        path = self._strategy.execute(src_path, dst_path, dst_dir)
        return path
