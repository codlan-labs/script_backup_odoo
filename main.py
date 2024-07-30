import subprocess
from datetime import datetime
import os
import zipfile
import argparse
import requests
import json
from urllib.parse import urlencode
from pathlib import Path

parser = argparse.ArgumentParser(description='Backup script')
parser.add_argument('-O','--odoo-container', help="Contenedor de Odoo",required=True)
parser.add_argument('-D','--database-container', help="Contenedor de Base de datos",required=True)
parser.add_argument('-d','--database', help="Nombre de base de datos",required=True)
parser.add_argument('-U','--pg-user', help="Postgres User",required=True)
parser.add_argument('-X','--pg-password', help="Postgres Password",required=True)
parser.add_argument('-s','--api-endpoint-service', help="API de Servicio de backup",required=True)
parser.add_argument('-k','--api-key', help="API Key de Servicio de backup",required=True)

args = parser.parse_args()
odoo_container = args.odoo_container
database_container = args.database_container
database = args.database
pg_user = args.pg_user
pg_password = args.pg_password
api_endpoint_service = args.api_endpoint_service
api_key = args.api_key

def backup_from_containers(odoo_container,db_container,dbname,user,password,host="localhost",port=5432):
    backup_file = "/tmp/dump.sql"
    path_current = os.getcwd()

    if not os.path.isdir(f"./backup_{dbname}"):
        command_create_backup = [
            "mkdir",f"backup_{dbname}"
        ]
        subprocess.run(command_create_backup, check=True)

    command = [
        "docker", "exec", "-i", db_container,
        "pg_dump",
        f"--dbname=postgresql://{user}:{password}@{host}:{port}/{dbname}",
        "-f", backup_file
    ]
    command_cp = [
        "docker","cp",f"{db_container}:{backup_file}",f"./backup_{dbname}"
    ]

    command_rm = [
        "docker", "exec", "-i", db_container,"rm","-rf",backup_file
    ]
    command_cp_filestore = [
        "docker","cp",f"{odoo_container}:/var/lib/odoo/filestore/{dbname}",f"./backup_{dbname}"
    ]

    command_zip = [
        "zip","-r","-m",f"backup_{dbname}.zip","dump.sql","filestore"
    ]

    # Ejecutar el comando
    try:
        subprocess.run(command, check=True)
        subprocess.run(command_cp, check=True)
        subprocess.run(command_rm, check=True)
        subprocess.run(command_cp_filestore, check=True)
        os.rename(f"{path_current}/backup_{dbname}/{dbname}",f"{path_current}/backup_{dbname}/filestore")
        subprocess.run(command_zip, check=True,cwd=f"{path_current}/backup_{dbname}")

        print(f"Backup completado exitosamente: {backup_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error al realizar el backup: {e}")

    return f"{path_current}/backup_{dbname}/backup_{dbname}.zip"

filename_backup = backup_from_containers(odoo_container,database_container,database,pg_user,pg_password)



with open(filename_backup, "rb") as backup:
    filesize = os.path.getsize(filename_backup)

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
