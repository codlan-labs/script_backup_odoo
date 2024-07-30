import argparse
import requests
import json
from urllib.parse import urlencode
import requests
from pathlib import Path

parser = argparse.ArgumentParser(description='Backup script')
parser.add_argument('-H','--host', help="Host de Instancia de Odoo",required=True)
parser.add_argument('-d','--database', help="Nombre de base de datos",required=True)
parser.add_argument('-p','--password', help="Password Maestro",required=True)
parser.add_argument('-P','--path', help="Directorio de destino",required=True)
parser.add_argument('-s','--api-endpoint-service', help="API de Servicio de backup",required=True)
parser.add_argument('-k','--api-key', help="API Key de Servicio de backup",required=True)

args = parser.parse_args()
host = args.host
database = args.database
password = args.password
path = args.path
api_endpoint_service = args.api_endpoint_service
api_key = args.api_key


payload = {"master_pwd": password, "name": database,"backup_format":"zip"}
backup_url = f"{host}/web/database/backup"
filename_backup = f"{path}/{database}.zip"
with requests.post(backup_url, 
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=urlencode(payload)) as backup_response:
    backup_response.raise_for_status()
    
    with open(filename_backup, "wb") as backup:
        for chunk in backup_response.iter_content(chunk_size=8192):
            backup.write(chunk)

    filesize = len(backup_response.content)
    print(filesize)
    #1. Obtener las urls prefirmadas para subida
    with open(filename_backup, "rb") as backup:
        with requests.post(f"{api_endpoint_service}/get_signed_upload_url",
                                headers={"Content-Type": "application/json","apiKey":api_key},
                                data=json.dumps({"params":{"filesize":filesize}})) as response_urls:
            response_urls.raise_for_status()
            result = response_urls.json().get("result")

            urls = result.get("urls")
            filename = result.get("filename")
            upload_id = result.get("upload_id")
            max_size = result.get("max_size")
            print(result)
            parts = []
            for num, url in enumerate(urls):
                part = num + 1
                file_data = backup.read(max_size)
                res_part = requests.put(url, data=file_data)

                if res_part.status_code != 200:
                    print(f"Error al subir parte {part}")
                    break

                etag = res_part.headers.get("ETag")
                parts.append({"ETag":etag,"PartNumber":part})
            
            requests.post(f"{api_endpoint_service}/combine_multiparts",
                            data=json.dumps({"params":{"upload_id":upload_id,"filename":filename,"parts":parts}}),
                            headers={"Content-Type": "application/json","apiKey":api_key})

