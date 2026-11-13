from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, AdminPasswordChangeForm
from .models import Expediente


class CustomUserCreationForm(UserCreationForm):
    """
    Formulario de creación de usuario en el panel de administración
    sin textos ni condiciones de validación debajo de los campos de contraseña.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'password1' in self.fields:
            self.fields['password1'].help_text = ''
        if 'password2' in self.fields:
            self.fields['password2'].help_text = ''


class CustomAdminPasswordChangeForm(AdminPasswordChangeForm):
    """
    Formulario de cambio de contraseña en el panel de administración
    sin textos ni condiciones debajo de los campos.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'password1' in self.fields:
            self.fields['password1'].help_text = ''
        if 'password2' in self.fields:
            self.fields['password2'].help_text = ''


# Re-registrar el modelo User con los formularios limpios de condiciones
admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    change_password_form = CustomAdminPasswordChangeForm


@admin.register(Expediente)
class ExpedienteAdmin(admin.ModelAdmin):
    list_display = (
        'nro',
        'expediente',
        'fecha',
        'nombre_archivo',
        'tipo_nombre',
        'tiene_adjunto',
        'ubicado',
    )
    list_filter = (
        'ano',
        'tipo_nombre',
        'tiene_adjunto',
        'ubicado',
    )
    search_fields = (
        'nombre_archivo',
        'expediente',
        'responsable_iniciador',
        'responsable_emisor',
        'responsable_receptor',
        'observaciones',
    )
    readonly_fields = (
        'secuencial',
        'fecha_nombre',
        'nombre_normalizado',
        'expediente_normalizado',
        'tipo_nombre',
        'tiene_adjunto',
    )
    ordering = ('-fecha',)
    list_per_page = 50
    date_hierarchy = 'fecha'

