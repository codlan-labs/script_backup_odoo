1. Crear entorno virtual
python3 -m venv venv

2. Instalar zip
apt install zip

3. Instalar requerimientos
python3 -m pip install -r requirements.txt

Entender los parámetros de ejecución:
-O: Nombre de contenedor de odoo
-D: Nombre de contenedor de base de datos de odoo
-d: Nombre de base de datos de postgres
-U: Usuario de base de datos de odoo
-X: Contraseña de base de datos de odoo
-s: Endopoint de servicio de backups
-k: API Key de autenticación

4. agregar a cron
Ejecutar
crontab -e
Agregar línea
0 0 * * *  /path/usr/bin/python3 /path/script_backup/main.py -O bo_16 -D bo16_db -d inn.7junio -U odoo_db -X odoo_db -s "http://localhost:9013" -k "a549dd9b-*****-****-****-*********"
