# Script de Backup para Odoo con Carga Multipart a AWS S3

Script automatizado en Python para generar backups de instancias de **Odoo** que se ejecutan en contenedores **Docker** y subirlos de forma eficiente a **Amazon S3** mediante un servicio API REST de Odoo (`manage_backups_s3`).

El script optimiza el espacio de almacenamiento y tiempo de transferencia permitiendo separar el dump de base de datos (`dump.sql`) del almacenamiento de archivos (`filestore`).

---

## 🚀 Características Principales

- **Separación de componentes (Modo `split`)**:
  - **Base de datos**: Se genera el `dump.sql` comprimido y se sube con timestamp (`<suffix>-db-<YYYY-MM-DD-HH-MM-SS>.zip`), manteniendo el histórico de versiones.
  - **Filestore**: Se comprime el directorio `/var/lib/odoo/filestore/<db>` y se sube con nombre estático (`<suffix>-filestore.zip`), sobreescribiendo y actualizándose en S3 en su mismo lugar.
- **Gestión eficiente de disco**: Limpieza inmediata de archivos temporales locales conforme se sube cada parte.
- **Carga Multipart en S3**: Soporta archivos de gran tamaño dividiéndolos en fragmentos (`multipart upload`) mediante URLs prefirmadas.
- **Múltiples modos de operación**: `split`, `full`, `db-only`, `filestore-only`.

---

## 📋 Requisitos Previos

1. **Docker**: Acceso al socket de Docker y permisos para ejecutar comandos `docker exec` y `docker cp`.
2. **Utilidad `zip`**: Para empaquetar los archivos de backup en el host.
   ```bash
   sudo apt-get update && sudo apt-get install -y zip
   ```
3. **Python 3.8+** con `pip` y entorno virtual.

---

## ⚙️ Instalación

1. Clonar o descargar el repositorio en el servidor host:
   ```bash
   cd /mnt/script_backup_odoo
   ```

2. Crear y activar un entorno virtual de Python:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Instalar las dependencias de Python:
   ```bash
   pip install -r requirements.txt
   ```

---

## 🛠️ Parámetros de Línea de Comandos

| Parámetro | Flag Corto | Obligatorio | Descripción |
| :--- | :--- | :---: | :--- |
| `--odoo-container` | `-O` | **Sí** | Nombre o ID del contenedor Docker de Odoo. |
| `--database-container` | `-D` | **Sí** | Nombre o ID del contenedor Docker de PostgreSQL. |
| `--database` | `-d` | **Sí** | Nombre de la base de datos de Odoo/PostgreSQL. |
| `--pg-user` | `-U` | **Sí** | Usuario de la base de datos PostgreSQL. |
| `--pg-password` | `-X` | **Sí** | Contraseña del usuario PostgreSQL. |
| `--api-endpoint-service` | `-s` | **Sí** | URL base del servidor Odoo con el módulo `manage_backups_s3` (ej. `https://www.midominio.com`). |
| `--api-key` | `-k` | **Sí** | API Key del directorio configurado en Odoo para la autenticación. |
| `--mode` | `-m` | No | Modo de backup: `full` (default), `split`, `db-only`, `filestore-only`. |

---

## 🔄 Modos de Ejecución (`--mode`)

### 1. Modo Dividido (`split`) — *Recomendado*
Genera dos subidas independientes:
1. Extrae `dump.sql`, lo comprime a `.zip` y lo sube con fecha como un nuevo registro histórico.
2. Limpia el temporal del dump.
3. Copia el `filestore`, lo comprime y lo sube con clave fija para sobreescribir el filestore anterior en S3.
4. Limpia el temporal del filestore.

### 2. Modo Completo (`full`) — *Compatibilidad Histórica*
Genera un único archivo `.zip` que contiene tanto `dump.sql` como el directorio `filestore/` juntos, subiéndolo con fecha.

### 3. Modo Solo Base de Datos (`db-only`)
Solo extrae, comprime y sube el dump de la base de datos con timestamp.

### 4. Modo Solo Filestore (`filestore-only`)
Solo extrae, comprime y sobreescribe el filestore en S3.

---

## 💡 Ejemplos de Uso

### Ejemplo 1: Backup Dividido (DB histórico + Filestore sobreescrito)
```bash
/mnt/script_backup_odoo/venv/bin/python3 /mnt/script_backup_odoo/main.py \
  -O "odoo_app_container" \
  -D "postgres_db_container" \
  -d "mi_base_datos" \
  -U "odoo_user" \
  -X "mi_password_seguro" \
  -s "https://backups.servidor.com" \
  -k "701c3ef9-502c-43d8-b934-194ecf327d29" \
  -m split
```

### Ejemplo 2: Solo Base de Datos (ej. ejecuciones frecuentes cada hora)
```bash
/mnt/script_backup_odoo/venv/bin/python3 /mnt/script_backup_odoo/main.py \
  -O "odoo_app_container" \
  -D "postgres_db_container" \
  -d "mi_base_datos" \
  -U "odoo_user" \
  -X "mi_password_seguro" \
  -s "https://backups.servidor.com" \
  -k "701c3ef9-502c-43d8-b934-194ecf327d29" \
  -m db-only
```

### Ejemplo 3: Solo Filestore
```bash
/mnt/script_backup_odoo/venv/bin/python3 /mnt/script_backup_odoo/main.py \
  -O "odoo_app_container" \
  -D "postgres_db_container" \
  -d "mi_base_datos" \
  -U "odoo_user" \
  -X "mi_password_seguro" \
  -s "https://backups.servidor.com" \
  -k "701c3ef9-502c-43d8-b934-194ecf327d29" \
  -m filestore-only
```

---

## ⏰ Automatización con Crontab

Puedes programar la ejecución periódica del script editando el crontab del sistema:

```bash
crontab -e
```

### Ejemplo de programación:
```cron
# Backup split diario a las 02:00 AM (DB con fecha + filestore sobreescrito)
0 2 * * * /mnt/script_backup_odoo/venv/bin/python3 /mnt/script_backup_odoo/main.py -O "odoo_container" -D "postgres_container" -d "odoo_prod" -U "odoo" -X "secret" -s "https://backups.servidor.com" -k "API_KEY_AQUI" -m split >> /var/log/odoo_backup.log 2>&1
```
