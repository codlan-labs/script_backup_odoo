1. Crear entorno virtual
python3 -m venv venv

2. Instalar requerimientos
python3 -m pip install -r requirements.txt

Parámetros de ejecución:
-H, --host: Host de la instancia de Odoo
-d, --database: Nombre de la base de datos
-p, --password: Contraseña del usuario administrador
-P, --path: Ruta donde se almacenarán los backups
-s, --server: Endpoint Servidor de almacenamiento
-k, --key: Clave de acceso al servidor de almacenamiento

3. agregar a cron
Ejecutra
crontab -e
Agregar línea
0 0 * * *  /path/usr/bin/python3 /path/script_backup/main.py -H "https://instanciaodoo" -d "nombrebasedatos" -p "**************************" -P "/path/backups" -s "https://codlan.com" -k "c7e41f4f-****-******"
