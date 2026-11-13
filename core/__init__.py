import pymysql

# Fix para compatibilidad de versión requerida por Django 4.2+
pymysql.version_info = (1, 4, 3, "final", 0)
pymysql.install_as_MySQLdb()

