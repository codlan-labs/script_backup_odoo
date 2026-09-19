import subprocess
from datetime import datetime
import os
import zipfile
import argparse
import requests
import json
import shutil
from pathlib import Path

parser = argparse.ArgumentParser(description='Backup script para Odoo y S3')
parser.add_argument('-O', '--odoo-container', help="Contenedor de Odoo", required=True)
parser.add_argument('-D', '--database-container', help="Contenedor de Base de datos", required=True)
parser.add_argument('-d', '--database', help="Nombre de base de datos", required=True)
parser.add_argument('-U', '--pg-user', help="Postgres User", required=True)
parser.add_argument('-X', '--pg-password', help="Postgres Password", required=True)
parser.add_argument('-s', '--api-endpoint-service', help="API de Servicio de backup", required=True)
parser.add_argument('-k', '--api-key', help="API Key de Servicio de backup", required=True)
parser.add_argument('-m', '--mode', 
                    choices=['full', 'split', 'db-only', 'filestore-only'], 
                    default='full', 
                    help="Modo de backup: full (zip único con dump + filestore), split (dump con fecha + filestore separado y sobreescrito), db-only (solo dump con fecha), filestore-only (solo filestore)")

args = parser.parse_args()
odoo_container = args.odoo_container
database_container = args.database_container
database = args.database
pg_user = args.pg_user
pg_password = args.pg_password
api_endpoint_service = args.api_endpoint_service
api_key = args.api_key
mode = args.mode


def ensure_backup_dir(dbname):
    path_current = os.getcwd()
    backup_dir = os.path.join(path_current, f"backup_{dbname}")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def backup_database_only(db_container, dbname, user, password, host="localhost", port=5432):
    backup_dir = ensure_backup_dir(dbname)
    backup_file_tmp = "/tmp/dump.sql"
    local_dump = os.path.join(backup_dir, "dump.sql")
    zip_path = os.path.join(backup_dir, f"backup_{dbname}_db.zip")

    if os.path.exists(zip_path):
        os.remove(zip_path)

    command_dump = [
        "docker", "exec", "-i", db_container,
        "pg_dump",
        f"--dbname=postgresql://{user}:{password}@{host}:{port}/{dbname}",
        "-f", backup_file_tmp
    ]
    command_cp = [
        "docker", "cp", f"{db_container}:{backup_file_tmp}", local_dump
    ]
    command_rm = [
        "docker", "exec", "-i", db_container, "rm", "-rf", backup_file_tmp
    ]
    command_zip = [
        "zip", "-r", "-m", f"backup_{dbname}_db.zip", "dump.sql"
    ]

    try:
        print(f"Extrayendo dump de base de datos '{dbname}'...")
        subprocess.run(command_dump, check=True)
        subprocess.run(command_cp, check=True)
        subprocess.run(command_rm, check=True)
        print("Comprimiendo dump.sql...")
        subprocess.run(command_zip, check=True, cwd=backup_dir)
        print(f"Backup de base de datos generado: {zip_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error al realizar el backup de base de datos: {e}")
        raise e

    return zip_path


def backup_filestore_only(odoo_container, dbname):
    backup_dir = ensure_backup_dir(dbname)
    target_filestore = os.path.join(backup_dir, "filestore")
    zip_path = os.path.join(backup_dir, f"backup_{dbname}_filestore.zip")

    if os.path.exists(zip_path):
        os.remove(zip_path)
    if os.path.exists(target_filestore):
        shutil.rmtree(target_filestore)

    command_cp_filestore = [
        "docker", "cp", f"{odoo_container}:/var/lib/odoo/filestore/{dbname}", backup_dir
    ]
    command_zip = [
        "zip", "-r", "-m", f"backup_{dbname}_filestore.zip", "filestore"
    ]

    try:
        print(f"Copiando filestore de '{dbname}' desde el contenedor '{odoo_container}'...")
        subprocess.run(command_cp_filestore, check=True)
        copied_path = os.path.join(backup_dir, dbname)
        if os.path.exists(copied_path):
            os.rename(copied_path, target_filestore)

        print("Comprimiendo filestore...")
        subprocess.run(command_zip, check=True, cwd=backup_dir)
        print(f"Backup de filestore generado: {zip_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error al realizar el backup de filestore: {e}")
        raise e

    return zip_path


def backup_full(odoo_container, db_container, dbname, user, password, host="localhost", port=5432):
    backup_dir = ensure_backup_dir(dbname)
    backup_file_tmp = "/tmp/dump.sql"
    local_dump = os.path.join(backup_dir, "dump.sql")
    target_filestore = os.path.join(backup_dir, "filestore")
    zip_path = os.path.join(backup_dir, f"backup_{dbname}.zip")

    if os.path.exists(zip_path):
        os.remove(zip_path)
    if os.path.exists(target_filestore):
        shutil.rmtree(target_filestore)

    command_dump = [
        "docker", "exec", "-i", db_container,
        "pg_dump",
        f"--dbname=postgresql://{user}:{password}@{host}:{port}/{dbname}",
        "-f", backup_file_tmp
    ]
    command_cp = [
        "docker", "cp", f"{db_container}:{backup_file_tmp}", local_dump
    ]
    command_rm = [
        "docker", "exec", "-i", db_container, "rm", "-rf", backup_file_tmp
    ]
    command_cp_filestore = [
        "docker", "cp", f"{odoo_container}:/var/lib/odoo/filestore/{dbname}", backup_dir
    ]
    command_zip = [
        "zip", "-r", "-m", f"backup_{dbname}.zip", "dump.sql", "filestore"
    ]

    try:
        print(f"Generando backup completo (DB + Filestore) para '{dbname}'...")
        subprocess.run(command_dump, check=True)
        subprocess.run(command_cp, check=True)
        subprocess.run(command_rm, check=True)
        subprocess.run(command_cp_filestore, check=True)

        copied_path = os.path.join(backup_dir, dbname)
        if os.path.exists(copied_path):
            os.rename(copied_path, target_filestore)

        subprocess.run(command_zip, check=True, cwd=backup_dir)
        print(f"Backup completo generado: {zip_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error al realizar el backup completo: {e}")
        raise e

    return zip_path


def upload_file_to_s3(filepath, api_endpoint, key_api, backup_type="full"):
    filesize = os.path.getsize(filepath)
    print(f"\nIniciando subida a S3 de '{filepath}' ({filesize} bytes) con backup_type='{backup_type}'...")

    response = requests.post(
        f"{api_endpoint}/get_signed_upload_url",
        headers={"Content-Type": "application/json", "apiKey": key_api},
        data=json.dumps({"params": {"filesize": filesize, "backup_type": backup_type}})
    )
    response.raise_for_status()
    result = response.json().get("result")

    if not result or isinstance(result, str):
        raise Exception(f"Respuesta no válida del servicio al obtener URLs: {result}")

    urls = result.get("urls", [])
    filename = result.get("filename")
    upload_id = result.get("upload_id")
    max_size = result.get("max_size", 1024 * 1024 * 1024)

    print(f"Obtenidas {len(urls)} partes de carga para '{filename}'. Subiendo...")
    parts = []
    with open(filepath, "rb") as backup_data:
        for num, url in enumerate(urls):
            part = num + 1
            file_data = backup_data.read(max_size)
            res_part = requests.put(url, data=file_data)

            if res_part.status_code != 200:
                raise Exception(f"Error al subir parte {part}. Código: {res_part.status_code}")

            etag = res_part.headers.get("ETag")
            parts.append({"ETag": etag, "PartNumber": part})
            print(f"Parte {part}/{len(urls)} subida exitosamente.")

    combine_res = requests.post(
        f"{api_endpoint}/combine_multiparts",
        data=json.dumps({
            "params": {
                "upload_id": upload_id,
                "filename": filename,
                "parts": parts,
                "backup_type": backup_type
            }
        }),
        headers={"Content-Type": "application/json", "apiKey": key_api}
    )
    combine_res.raise_for_status()
    print(f"Subida completada y combinada exitosamente en S3: {filename}")


def clean_up_path(path):
    if os.path.exists(path):
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


# ---------------------------
# Ejecución Principal
# ---------------------------
backup_dir = os.path.join(os.getcwd(), f"backup_{database}")

try:
    if mode == 'full':
        zip_file = backup_full(odoo_container, database_container, database, pg_user, pg_password)
        upload_file_to_s3(zip_file, api_endpoint_service, api_key, backup_type='full')
        clean_up_path(zip_file)

    elif mode == 'split':
        # 1. Base de datos (dump.sql zipeado con fecha)
        db_zip = backup_database_only(database_container, database, pg_user, pg_password)
        upload_file_to_s3(db_zip, api_endpoint_service, api_key, backup_type='db')
        clean_up_path(db_zip)

        # 2. Filestore (zipeado aparte y sobreescrito en S3)
        filestore_zip = backup_filestore_only(odoo_container, database)
        upload_file_to_s3(filestore_zip, api_endpoint_service, api_key, backup_type='filestore')
        clean_up_path(filestore_zip)

    elif mode == 'db-only':
        db_zip = backup_database_only(database_container, database, pg_user, pg_password)
        upload_file_to_s3(db_zip, api_endpoint_service, api_key, backup_type='db')
        clean_up_path(db_zip)

    elif mode == 'filestore-only':
        filestore_zip = backup_filestore_only(odoo_container, database)
        upload_file_to_s3(filestore_zip, api_endpoint_service, api_key, backup_type='filestore')
        clean_up_path(filestore_zip)

finally:
    # Limpieza final del directorio de trabajo temporal si quedó vacío o residual
    clean_up_path(backup_dir)

print("\n=== Proceso de backup finalizado con éxito ===")