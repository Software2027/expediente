from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Crea o actualiza un superusuario administrador con contraseña hasheada de forma segura (PBKDF2/SHA-256).'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', type=str, default='admin', help='Nombre de usuario (por defecto: admin)')
        parser.add_argument('--clave', type=str, default='admin1234', help='Contraseña del superusuario (por defecto: admin1234)')
        parser.add_argument('--email', type=str, default='admin@municipalidad.gov.ar', help='Correo electrónico')

    def handle(self, *args, **options):
        username = options['usuario'].strip()
        password = options['clave'].strip()
        email = options['email'].strip()

        if not username or not password:
            self.stderr.write(self.style.ERROR("El usuario y la contraseña no pueden estar vacíos."))
            return

        usuario, creado = User.objects.get_or_create(username=username, defaults={'email': email})

        # set_password hashea la contraseña automáticamente usando PBKDF2-SHA256 con salt única
        usuario.set_password(password)
        usuario.email = email
        usuario.is_staff = True
        usuario.is_superuser = True
        usuario.is_active = True
        usuario.save()

        if creado:
            self.stdout.write(self.style.SUCCESS(f"[OK] Superusuario '{username}' creado exitosamente con contraseña hasheada."))
        else:
            self.stdout.write(self.style.SUCCESS(f"[OK] Superusuario '{username}' actualizado exitosamente con nueva contraseña hasheada."))

