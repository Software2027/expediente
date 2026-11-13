"""
Script utilitario para ejecutar migraciones e importaciones en cPanel sin terminal SSH.
Se puede ejecutar vía:
1) Tareas Cron de cPanel (Recomendado para evitar límites de tiempo de Apache).
2) Desde la opción de comando de Setup Python App si tu cPanel la tiene.
"""
import os
import sys
import datetime

# 1. Configuración del entorno Django
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

LOG_FILE = os.path.join(BASE_DIR, 'cpanel_ejecucion.log')

def log(mensaje):
    ahora = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    linea = f"[{ahora}] {mensaje}"
    print(linea)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(linea + '\n')

def main():
    log("=== INICIANDO SCRIPT DE CONFIGURACIÓN EN CPANEL ===")
    
    try:
        import django
        django.setup()
        from django.core.management import call_command
        log("Django inicializado correctamente.")
    except Exception as e:
        log(f"ERROR al inicializar Django: {e}")
        return

    # Paso 1: Ejecutar migraciones para asegurar que existan las tablas
    log("--- Paso 1: Ejecutando migraciones (migrate) ---")
    try:
        call_command('migrate', interactive=False)
        log("[OK] Migraciones aplicadas con éxito.")
    except Exception as e:
        log(f"ERROR en migraciones: {e}")
        return

    # Paso 1.1: Crear o asegurar el superusuario administrador inicial con clave hasheada
    log("--- Paso 1.1: Creando superusuario administrador inicial ---")
    try:
        # Podés cambiar el usuario y contraseña inicial si lo deseas antes de subirlo
        call_command('crear_admin', usuario='admin', clave='admin1234')
        log("[OK] Superusuario 'admin' configurado con contraseña hasheada.")
    except Exception as e:
        log(f"ERROR al configurar superusuario: {e}")

    # Paso 2: Importar todos los reportes desde la carpeta reportes/
    log("--- Paso 2: Ejecutando importación masiva de reportes ---")
    carpeta_reportes = os.path.join(BASE_DIR, 'reportes')
    if os.path.exists(carpeta_reportes):
        try:
            # Ejecuta la importación limpia y reconstruye Área Destino
            call_command('importar_todos_reportes', '--limpiar', carpeta=carpeta_reportes)
            log("[OK] Importación de reportes finalizada con éxito.")
        except Exception as e:
            log(f"ERROR durante la importación: {e}")
    else:
        log(f"AVISO: No se encontró la carpeta '{carpeta_reportes}'. Verificá haber subido los archivos .xlsx.")

    # Paso 3: Verificar cantidad de registros guardados
    try:
        from expedientes.models import Expediente
        total = Expediente.objects.count()
        con_dest = Expediente.objects.exclude(area_destino__isnull=True).exclude(area_destino='').count()
        con_adj = Expediente.objects.filter(tiene_adjunto=True).count()
        log(f"--- RESUMEN FINAL EN BASE DE DATOS ---")
        log(f"Total registros: {total:,}")
        log(f"Con Area Destino: {con_dest:,}")
        log(f"Con Adjunto: {con_adj:,}")
    except Exception as e:
        log(f"ERROR al consultar estadísticas finales: {e}")

    log("=== PROCESO FINALIZADO. Ya podés revisar tu sitio en cPanel ===")

if __name__ == '__main__':
    main()

