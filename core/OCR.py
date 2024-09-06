import json, sqlite3
from typing import List, Dict, Optional, Union
import polars as pl
from sqlalchemy import create_engine
from unstructured_client import UnstructuredClient
from unstructured_client.models import operations, shared


class OCR:
    def __init__(self, current_df: Optional[pl.DataFrame] = None):
        self.unstructured_client = UnstructuredClient(server_url="http://localhost:8000")
        self.current_df = current_df


    def get_ocr(self, file_path: str) -> List[Dict]:
        with open(file_path, "rb") as f:
            data = f.read()

        req = operations.PartitionRequest(
            partition_parameters=shared.PartitionParameters(
                files=shared.Files(
                    content=data,
                    file_name=file_path,
                ),
                strategy=shared.Strategy.HI_RES,
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

    def text_chunks_to_dataframe(self, json_data: List[Dict]) -> pl.DataFrame:
        # Agrupar los elementos por número de página
        pages = {}
        for item in json_data:
            page_number = item['metadata']['page_number']
            if page_number not in pages:
                pages[page_number] = []
            pages[page_number].append(item['text'])
        
        # Crear una lista de diccionarios con la estructura deseada
        data = []
        for page_number, texts in pages.items():
            data.append({
                'metadata': json.dumps({'page_number': page_number, 'filename': json_data[0]['metadata']['filename']}),
                'text': ' '.join(texts)
            })
        
        # Crear el DataFrame de Polars
        self.current_df = pl.DataFrame(data).with_row_index('id')
        
        return self.current_df
    

    def add_if_not_exists(self, new_data: Union[pl.DataFrame, Dict], key_columns: List = ['metadata', 'text']) -> pl.DataFrame:
        """
        Agrega nuevas filas al DataFrame si no existen basándose en columnas clave.
        
        :param df: DataFrame de Polars existente
        :param nuevos_datos: DataFrame o diccionario con los nuevos datos
        :param columnas_clave: Lista de nombres de columnas para verificar la existencia
        :return: DataFrame actualizado
        """
        # Si nuevos_datos es un diccionario, convertirlo a DataFrame
        if isinstance(new_data, dict):
            new_data = pl.DataFrame([new_data])
        if not isinstance(new_data, pl.DataFrame):
            raise TypeError("nuevos_datos debe ser un DataFrame de Polars o un diccionario")

        # Crear una expresión para verificar si los datos ya existen
        condition = pl.all_horizontal([
            pl.col(col).is_in(new_data[col])
            for col in key_columns
        ])

        # Filtrar los datos existentes
        existing_data = self.current_df.filter(condition)

        # Identificar los datos nuevos
        new = new_data.join(
            existing_data.select(key_columns),
            on=key_columns,
            how="anti"
        )

        # Si hay datos nuevos, agregarlos al DataFrame original
        if not new.is_empty():
            print(f"Se han encontrado datos nuevos para agregar")
            self.current_df = pl.concat([self.current_df, new], how="vertical")
        else:
            print("No hay datos nuevos para agregar")
        return self.current_df


    def save_checkpoint(self, checkpoint_path: str, table_name: Optional[str] = 'ocr_data') -> None:
        """
        Save the current DataFrame to a SQLite database checkpoint.

        This method saves the current DataFrame to a SQLite database checkpoint file. If the file already exists, it
        will be overwritten.

        Parameters:
            checkpoint_path (str): The path to the SQLite database checkpoint file.
        """

        conn = sqlite3.connect(checkpoint_path)
        temp_df = self.current_df.clone()
        temp_df.drop_in_place('id')
        temp_df.write_database(table_name=table_name, connection=f"sqlite:///{checkpoint_path}", if_table_exists="replace")
        conn.close()
    
    
    def load_checkpoint(self, checkpoint_path: str, table_name: Optional[str] = 'ocr_data') -> pl.DataFrame:
        conn = create_engine(f"sqlite:///{checkpoint_path}")
        query = f"SELECT * FROM {table_name}"
        self.current_df = pl.read_database(query=query, connection=conn.connect()).with_row_index('id')
        return self.current_df