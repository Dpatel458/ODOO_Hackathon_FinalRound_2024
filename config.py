# Configuration file for the Flask application
import secrets

SECRET_KEY = secrets.token_hex(16)


MYSQL_HOST = '127.0.0.1'
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'root'
MYSQL_DB = 'library'
