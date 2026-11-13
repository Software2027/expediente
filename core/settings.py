from pathlib import Path

# Construcción de rutas relativas dentro del proyecto
# BASE_DIR apunta a la raíz del proyecto (c:\OCTAVIO\Muni\expedientes)
BASE_DIR = Path(__file__).resolve().parent.parent

# Clave secreta para desarrollo (en producción migrar a variables de entorno)
SECRET_KEY = 'django-insecure-muni#expedientes!2026$k7z9@w4x1q8p0v5b3c2m6j8y'

# ADVERTENCIA DE SEGURIDAD: ¡no ejecutar con DEBUG activado en producción!
DEBUG = True  # Cambiar a False en el entorno de producción (cPanel)

# Hosts permitidos. En producción, especificar los dominios/subdominios exactos de cPanel
ALLOWED_HOSTS = ['*']  # Restringir en producción, ej: ['expedientes.mimunicipio.gob.ar', 'localhost']

# Definición de aplicaciones instaladas
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Aplicaciones locales
    'expedientes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Configuración de base de datos MySQL usando PyMySQL como driver
# IMPORTANTE: Reemplazar NAME, USER y PASSWORD por las credenciales reales creadas en cPanel MySQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'usuario_expedientes',        # Nombre de la base de datos en cPanel (ej: cpaneluser_expedientes)
        'USER': 'root',               # Usuario MySQL de cPanel (ej: cpaneluser_muni)
        'PASSWORD': '',     # Contraseña asignada al usuario MySQL
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# Validación de contraseñas desactivada para permitir cualquier clave sin restricciones ni condiciones en el formulario
AUTH_PASSWORD_VALIDATORS = []

# Internacionalización y localización
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Cordoba'
USE_I18N = True
USE_TZ = True

# Archivos estáticos (CSS, JavaScript, imágenes del diseño)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Archivos subidos por los usuarios (media)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Tipo de campo clave primaria predeterminado
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redirecciones de autenticación
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'expedientes:buscador'
LOGOUT_REDIRECT_URL = 'login'

# Configuración de sesión (expiración a los 30 minutos de inactividad)
SESSION_COOKIE_AGE = 1800  # 30 minutos en segundos (30 * 60)
SESSION_SAVE_EVERY_REQUEST = True  # Renueva los 30 minutos con cada clic o interacción
SESSION_EXPIRE_AT_BROWSER_CLOSE = False


