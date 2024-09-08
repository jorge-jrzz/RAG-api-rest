import json
from pathlib import Path
from typing import List, Dict
from unstructured_client import UnstructuredClient
from unstructured_client.models import operations, shared


class OCR:
    def __init__(self):
        self.unstructured_client = UnstructuredClient(server_url="http://localhost:8000")


    def get_ocr(self, file_path: str) -> List[Dict]:
        with open(file_path, "rb") as f:
            data = f.read()

        req = operations.PartitionRequest(
            partition_parameters=shared.PartitionParameters(
                files=shared.Files(
                    content=data,
                    file_name=file_path,
                ),
                strategy=shared.Strategy.AUTO,
                languages=['eng', 'spa'],
                split_pdf_page=True,            # If True, splits the PDF file into smaller chunks of pages.
                split_pdf_allow_failed=True,    # If True, the partitioning continues even if some pages fail.
                split_pdf_concurrency_level=15  # Set the number of concurrent request to the maximum value: 15.
            ),
        )

        try:
            res = self.unstructured_client.general.partition(request=req)
            element_dicts = [element for element in res.elements]
            json_elements = json.dumps(element_dicts, indent=2)

            # Print the processed data.
            print(json_elements)
            return element_dicts

        except Exception as e:
            print(e)


    def get_dev_ocr(self, file_path: str) -> Dict:
        file = Path(file_path)
        metadata = {"filetype": f'text/{file.suffix[1:]}' , "filename": file.name}
        text = file.read_text(encoding='utf-8')
        data = {
            'metadata': metadata, 
            'text': text
        }
        return [data]
