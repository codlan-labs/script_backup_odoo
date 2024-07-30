import subprocess
from datetime import datetime
import os
import zipfile


def backup_from_containers(odoo_container,db_container,dbname,user,password,host="localhost",port=5432):
    # Datos de conexión
    """
    host = "localhost"  # Dirección del host del contenedor
    port = "5432"       # Puerto de PostgreSQL
    dbname = "inn.7jun.test2"  # Nombre de la base de datos
    user = "odoo_db"    # Usuario de PostgreSQL
    password = "odoo_db"  # Contraseña de PostgreSQL

    db_container = "bo16_db"  # Nombre del contenedor de la base de datos
    odoo_container = "bo_16"
    """
    # Nombre del archivo de backup con fecha
    backup_file = "/tmp/dump.sql"
    path_current = os.getcwd()

    # Comando para ejecutar pg_dump
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

path_backup = backup_from_containers("bo_16","bo16_db","inn.7jun.test2","odoo_db","odoo_db")