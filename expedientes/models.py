import os
import re
import unicodedata
from datetime import datetime
from django.db import models


class Expediente(models.Model):
    """
    Representa una fila del listado de expedientes/adjuntos.
    Cada registro corresponde a un adjunto (o expediente sin adjunto).
    """

    # --- CAMPOS ORIGINALES DEL EXCEL ---
    nro = models.IntegerField(null=True, blank=True, verbose_name='Nro.')
    id_origen = models.BigIntegerField(null=True, blank=True, verbose_name='ID')
    origen = models.CharField(max_length=50, null=True, blank=True, verbose_name='Origen')
    clave = models.BigIntegerField(null=True, blank=True, verbose_name='Clave')
    nombre_archivo = models.CharField(max_length=255, null=True, blank=True, db_index=True, verbose_name='Nombre de archivo')
    fecha = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name='Fecha')
    usuario = models.CharField(max_length=50, null=True, blank=True, verbose_name='Usuario')
    id_pase = models.BigIntegerField(null=True, blank=True, verbose_name='IdPase')
    id_cuerpo = models.BigIntegerField(null=True, blank=True, verbose_name='IdCuerpo')
    numero_pase = models.IntegerField(null=True, blank=True, verbose_name='Número de Pase')
    id_expediente = models.BigIntegerField(null=True, blank=True, verbose_name='IdExpediente')
    id_tipo_expediente = models.IntegerField(null=True, blank=True, verbose_name='IdTipoExpediente')
    tipo_expediente = models.CharField(max_length=100, null=True, blank=True, db_index=True, verbose_name='Tipo de Expediente')
    numero = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='Número')
    ano = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='Año')
    id_tipo_tramite = models.IntegerField(null=True, blank=True, verbose_name='IdTipoTramite')
    tipo_tramite = models.CharField(max_length=150, null=True, blank=True, db_index=True, verbose_name='Tipo de Trámite')
    cuerpo_numero = models.IntegerField(null=True, blank=True, verbose_name='Cuerpo Número')
    id_tipo_pase = models.IntegerField(null=True, blank=True, verbose_name='IdTipoPase')
    tipo_pase = models.CharField(max_length=100, null=True, blank=True, verbose_name='Tipo de Pase')
    id_responsable_emisor = models.CharField(max_length=20, null=True, blank=True, verbose_name='Id Responsable Emisor')
    responsable_emisor = models.CharField(max_length=150, null=True, blank=True, db_index=True, verbose_name='Responsable Emisor')
    id_area_destino = models.IntegerField(null=True, blank=True, verbose_name='Id Área Destino')
    area_destino = models.CharField(max_length=150, null=True, blank=True, db_index=True, verbose_name='Área Destino')
    fecha_realizacion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha Realización')
    fecha_recepcion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha Recepción')
    fecha_registro = models.DateTimeField(null=True, blank=True, verbose_name='Fecha Registro')
    fecha_actualizacion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha Actualización')
    id_responsable_receptor = models.CharField(max_length=20, null=True, blank=True, verbose_name='Id Responsable Receptor')
    responsable_receptor = models.CharField(max_length=150, null=True, blank=True, db_index=True, verbose_name='Responsable Receptor')
    observaciones = models.TextField(null=True, blank=True, verbose_name='Observaciones')
    folios = models.IntegerField(null=True, blank=True, verbose_name='Folios')
    id_operador = models.CharField(max_length=20, null=True, blank=True, verbose_name='Id Operador')
    operador = models.CharField(max_length=150, null=True, blank=True, db_index=True, verbose_name='Operador')
    fecha_inicio = models.DateTimeField(null=True, blank=True, verbose_name='Fecha Inicio')
    area_iniciadora = models.CharField(max_length=150, null=True, blank=True, verbose_name='Área Iniciadora')
    responsable_iniciador = models.CharField(max_length=150, null=True, blank=True, db_index=True, verbose_name='Responsable Iniciador')
    expediente = models.CharField(max_length=50, null=True, blank=True, db_index=True, verbose_name='Expediente')

    # --- CAMPOS DERIVADOS (Calculados en save()) ---
    secuencial = models.CharField(max_length=20, blank=True, db_index=True, verbose_name='Secuencial')
    fecha_nombre = models.DateField(null=True, blank=True, db_index=True, verbose_name='Fecha en Nombre')
    nombre_normalizado = models.CharField(max_length=255, blank=True, db_index=True, verbose_name='Nombre Normalizado')
    expediente_normalizado = models.CharField(max_length=50, blank=True, db_index=True, verbose_name='Expediente Normalizado')
    tiene_adjunto = models.BooleanField(default=False, db_index=True, verbose_name='Tiene Adjunto')
    tipo_nombre = models.CharField(
        max_length=10,
        choices=[
            ('sistema', 'PDF del sistema'),
            ('persona', 'Nombre de persona/empresa'),
            ('generico', 'Genérico (IMAG, número suelto)'),
            ('vacio', 'Sin adjunto'),
        ],
        default='vacio',
        db_index=True,
        verbose_name='Tipo de Nombre'
    )

    # --- CAMPOS DE SEGUIMIENTO MANUAL ---
    ubicado = models.CharField(max_length=10, blank=True, verbose_name='Ubicado')  # OK / NO / DUDOSO
    ruta = models.CharField(max_length=500, blank=True, verbose_name='Ruta en Disco')
    fecha_busqueda = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Búsqueda')

    class Meta:
        db_table = 'expedientes'
        ordering = ['-fecha']
        verbose_name = 'Expediente'
        verbose_name_plural = 'Expedientes'
        indexes = [
            models.Index(fields=['ano', 'tipo_expediente']),
            models.Index(fields=['ano', 'fecha']),
            models.Index(fields=['ano', 'tipo_nombre']),
            models.Index(fields=['tiene_adjunto', 'ano']),
            models.Index(fields=['expediente_normalizado']),
            models.Index(fields=['secuencial']),
            models.Index(fields=['nombre_normalizado']),
            models.Index(fields=['fecha_nombre']),
        ]

    def __str__(self):
        return f"{self.expediente or 'sin-exp'} - {self.nombre_archivo or 'sin adjunto'}"

    @staticmethod
    def _normalizar(texto: str) -> str:
        """
        Normaliza una cadena de texto para facilitar búsquedas sin distinción
        de tildes, mayúsculas o caracteres de puntuación comunes:
        1. Convierte a minúsculas.
        2. Descompone caracteres Unicode (NFD) y remueve marcas diacríticas (tildes/acentos).
        3. Elimina puntos y comas.
        4. Colapsa múltiples espacios consecutivos en un único espacio y recorta bordes.
        """
        if not texto:
            return ''
        texto = texto.lower()
        # Normalizar caracteres con tilde a su forma básica
        texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
        # Reemplazar puntos y comas por nada
        texto = texto.replace('.', '').replace(',', '')
        # Colapsar espacios múltiples
        texto = re.sub(r'\s+', ' ', texto).strip()
        return texto

    def save(self, *args, **kwargs):
        # 1. Determinar si tiene adjunto
        self.tiene_adjunto = bool(self.nombre_archivo and self.nombre_archivo.strip())

        # 2. Inicializar valores calculados
        self.secuencial = ''
        self.fecha_nombre = None
        self.tipo_nombre = 'vacio'

        # 3. Clasificación de tipo de adjunto y extracción de metadatos
        if self.tiene_adjunto:
            nombre = self.nombre_archivo.strip()

            # a. Patrón de archivos autogenerados por el sistema municipal:
            # Estructura: _(MMDDAAAA)_(HHMMSS)_(SECUENCIAL).pdf
            # Ej: U64871A2X114823_11152024_084358_041877.pdf
            #   - Grupo 1 (\d{8}): Fecha en formato mes-día-año (MMDDAAAA)
            #   - Grupo 2 (\d{6}): Número secuencial de 6 dígitos que identifica la pieza
            patron_sistema = re.search(r'_(\d{8})_\d{6}_(\d{6})\.pdf$', nombre, re.IGNORECASE)

            if patron_sistema:
                self.tipo_nombre = 'sistema'
                self.secuencial = patron_sistema.group(2)
                fecha_str = patron_sistema.group(1)
                try:
                    self.fecha_nombre = datetime.strptime(fecha_str, '%m%d%Y').date()
                except ValueError:
                    self.fecha_nombre = None
            else:
                # b. Archivos manuales con extensión conocida
                extensiones_validas = ('.pdf', '.jpg', '.jpeg', '.png', '.zip', '.tif', '.tiff')
                nombre_lower = nombre.lower()
                tiene_extension = any(nombre_lower.endswith(ext) for ext in extensiones_validas)

                if tiene_extension:
                    base, _ = os.path.splitext(nombre)
                    # Detecta nombres genéricos de escáner o números sueltos (ej. IMAG0011, IMG_1234, Scan01, 12345)
                    if re.match(r'^(IMAG\d+|IMG_\d+|Scan\d+|\d+)$', base, re.IGNORECASE):
                        self.tipo_nombre = 'generico'
                    else:
                        self.tipo_nombre = 'persona'
                else:
                    # c. Sin extensión conocida
                    self.tipo_nombre = 'generico'

        # 4. Normalizar nombre de archivo para búsquedas eficientes
        self.nombre_normalizado = self._normalizar(self.nombre_archivo or '')

        # 5. Normalizar identificador de expediente
        # Si Excel convirtió el número a fecha (ej. "1900-01-01 00:00:00" o similar con timestamp)
        # y se dispone de número y año, reconstruye el formato canónico "AAAA-NNN-1"
        if self.expediente and ' 00:00:00' in self.expediente and self.numero and self.ano:
            self.expediente_normalizado = f"{self.ano}-{self.numero:03d}-1"
        else:
            self.expediente_normalizado = self.expediente.strip() if self.expediente else ''

        # 6. Guardar en base de datos
        super().save(*args, **kwargs)

