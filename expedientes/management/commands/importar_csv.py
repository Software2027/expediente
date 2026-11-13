import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from expedientes.models import Expediente


class Command(BaseCommand):
    help = 'Importa expedientes y adjuntos desde un archivo CSV o TSV (con o sin encabezados)'

    COLUMNAS_POSICIONALES = [
        'nro',                     # 0
        'id_origen',               # 1
        'origen',                  # 2
        'clave',                   # 3
        'nombre_archivo',          # 4
        'fecha',                   # 5
        'usuario',                 # 6
        'id_pase',                 # 7
        'id_cuerpo',               # 8
        'numero_pase',             # 9
        'id_expediente',           # 10
        'id_tipo_expediente',      # 11
        'tipo_expediente',         # 12
        'numero',                  # 13
        'ano',                     # 14
        'id_tipo_tramite',         # 15
        'tipo_tramite',            # 16
        'cuerpo_numero',           # 17
        'id_tipo_pase',            # 18
        'tipo_pase',               # 19
        'id_responsable_emisor',   # 20
        'responsable_emisor',      # 21
        'id_area_destino',         # 22
        'area_destino',            # 23
        'fecha_realizacion',       # 24
        'fecha_recepcion',         # 25
        'fecha_registro',          # 26
        'fecha_actualizacion',     # 27
        'id_responsable_receptor', # 28
        'responsable_receptor',    # 29
        'observaciones',           # 30 (opcional)
        'folios',                  # 31 (opcional)
        'id_operador',             # 32 (opcional)
        'operador',                # 33 (opcional)
        'fecha_inicio',            # 34 (opcional)
        'area_iniciadora',         # 35 (opcional)
        'responsable_iniciador',   # 36 (opcional)
        'expediente',              # 37 (opcional)
    ]

    ALIAS = {
        'nro': ['NRO', 'NRO.', 'ID_FILA', 'NRO_'],
        'id_origen': ['ID', 'ID_ORIGEN'],
        'origen': ['ORIGEN'],
        'clave': ['CLAVE'],
        'nombre_archivo': ['ARCHIVO_PASE_NOMBRE', 'ARCHIVO_PASE', 'NOMBRE', 'NOMBRE_ARCHIVO', 'ARCHIVO', 'ADJUNTO'],
        'fecha': ['FECHA_ARCHIVO', 'FECHA', 'FECHA_PASE'],
        'usuario': ['USUARIO'],
        'id_pase': ['IDPASE', 'ID_PASE'],
        'id_cuerpo': ['IDCUERPO', 'ID_CUERPO'],
        'numero_pase': ['NUMEROPASE', 'NUMERO_PASE'],
        'id_expediente': ['IDEXPEDIENTE', 'ID_EXPEDIENTE'],
        'id_tipo_expediente': ['IDTIPOEXPEDIENTE', 'ID_TIPO_EXPEDIENTE'],
        'tipo_expediente': ['TIPO_EXPEDIENTE', 'TIPOEXPEDIENTE'],
        'numero': ['NUMERO_EXPEDIENTE', 'NUMERO', 'NRO_EXPEDIENTE_NUMERO', 'NUMERO_EXPEDIENTE'],
        'ano': ['ANO_EXPEDIENTE', 'ANIO_EXPEDIENTE', 'ANO', 'ANIO'],
        'id_tipo_tramite': ['IDTIPOTRAMITE', 'ID_TIPO_TRAMITE'],
        'tipo_tramite': ['TIPO_TRAMITE', 'TIPOTRAMITE'],
        'cuerpo_numero': ['CUERPO_NRO', 'CUERPONUMERO', 'CUERPO_NUMERO'],
        'id_tipo_pase': ['IDTIPOPASE', 'ID_TIPO_PASE'],
        'tipo_pase': ['TIPOPASE', 'TIPO_PASE'],
        'id_responsable_emisor': ['IDRESPONSABLEEMISOR', 'ID_RESPONSABLE_EMISOR'],
        'responsable_emisor': ['RESPONSABLEEMISOR', 'RESPONSABLE_EMISOR'],
        'id_area_destino': ['IDAREADESTINO', 'ID_AREA_DESTINO'],
        'area_destino': ['AREADESTINO', 'AREA_DESTINO'],
        'fecha_realizacion': ['FECHAREALIZACION_PASE', 'FECHAREALIZACION', 'FECHA_REALIZACION'],
        'fecha_recepcion': ['FECHARECEPCION_PASE', 'FECHARECEPCION', 'FECHA_RECEPCION'],
        'fecha_registro': ['FECHAREGISTRO', 'FECHA_REGISTRO'],
        'fecha_actualizacion': ['FECHAACTUALIZACION', 'FECHA_ACTUALIZACION'],
        'id_responsable_receptor': ['IDRECEPTOR', 'IDRESPONSABLERECEPTOR', 'ID_RESPONSABLE_RECEPTOR'],
        'responsable_receptor': ['RECEPTOR', 'RESPONSABLERECEPTOR', 'RESPONSABLE_RECEPTOR'],
        'observaciones': ['OBSERVACIONES_PASE', 'OBSERVACIONES'],
        'folios': ['FOLIOS_PASE', 'FOLIOS'],
        'id_operador': ['IDOPERADOR', 'ID_OPERADOR'],
        'operador': ['OPERADOR'],
        'fecha_inicio': ['FECHAINICIO', 'FECHA_INICIO'],
        'area_iniciadora': ['AREA_INICIADORA', 'AREAINICIADORA'],
        'responsable_iniciador': ['RESPONSABLE_INICIADOR', 'RESPONSABLEINICIADOR'],
        'expediente': ['EXPEDIENTE', 'NRO_EXPEDIENTE'],
    }

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Ruta al archivo CSV o TSV')
        parser.add_argument(
            '--delimiter',
            type=str,
            default=None,
            help="Separador de campos (ej. '\\t', ';', ','). Si se omite, se autodetecta."
        )
        parser.add_argument(
            '--encoding',
            type=str,
            default=None,
            help='Codificación (ej. utf-8, latin-1). Si se omite, se prueba utf-8 y luego latin-1.'
        )
        parser.add_argument(
            '--sin-cabecera',
            action='store_true',
            help='Forzar a interpretar la primera fila como datos (sin encabezados).'
        )

    @staticmethod
    def _str(val):
        if val is None:
            return None
        texto = str(val).strip()
        if not texto or texto.lower() in ('null', 'none', 'nan'):
            return None
        return texto

    @staticmethod
    def _int(val):
        if val is None:
            return None
        texto = str(val).strip()
        if not texto or texto.lower() in ('null', 'none', 'nan'):
            return None
        try:
            return int(float(texto))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _dt(val):
        if val is None:
            return None
        cadena = str(val).strip()
        if not cadena or cadena.lower() in ('null', 'none', 'nan'):
            return None

        formatos = [
            '%Y-%m-%d %H:%M:%S',
            '%d/%m/%Y %I:%M:%S %p',
            '%d/%m/%Y %H:%M:%S',
            '%Y-%m-%d',
            '%d/%m/%Y',
        ]
        for fmt in formatos:
            try:
                dt = datetime.strptime(cadena, fmt)
                if timezone.is_naive(dt):
                    return timezone.make_aware(dt)
                return dt
            except ValueError:
                continue
        return None

    def detectar_separador_y_encoding(self, ruta_archivo, delimiter_arg, encoding_arg):
        encodings = [encoding_arg] if encoding_arg else ['utf-8', 'latin-1', 'cp1252']
        delimitadores = ['\t', ';', ','] if not delimiter_arg else [delimiter_arg]

        # Si el usuario pasó explícitamente '\t' como cadena de escape
        if delimiter_arg == '\\t':
            delimitadores = ['\t']

        for enc in encodings:
            try:
                with open(ruta_archivo, 'r', encoding=enc) as f:
                    muestra = f.read(4096)
                    if not muestra:
                        return enc, '\t'

                    if delimiter_arg:
                        return enc, '\t' if delimiter_arg == '\\t' else delimiter_arg

                    # Contar frecuencias de posibles separadores
                    conteos = {d: muestra.count(d) for d in delimitadores}
                    separador_elegido = max(conteos, key=conteos.get)
                    return enc, separador_elegido
            except (UnicodeDecodeError, LookupError):
                continue

        return 'latin-1', '\t'

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        sin_cabecera_flag = options['sin_cabecera']

        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f"El archivo no existe: {csv_path}"))
            return

        encoding_usado, delimiter_usado = self.detectar_separador_y_encoding(
            csv_path, options['delimiter'], options['encoding']
        )

        nombre_sep = "TABULADOR (\\t)" if delimiter_usado == '\t' else f"'{delimiter_usado}'"
        self.stdout.write(self.style.NOTICE(f"Leyendo archivo con codificación '{encoding_usado}' y separador {nombre_sep}..."))

        with open(csv_path, 'r', encoding=encoding_usado, errors='replace') as f:
            reader = csv.reader(f, delimiter=delimiter_usado)

            # Leer primera fila para determinar si tiene cabecera
            try:
                primera_fila = next(reader)
            except StopIteration:
                self.stdout.write(self.style.WARNING("El archivo está vacío."))
                return

            # Si el primer valor es un número entero (ej. '1') y no tiene flag explicito, interpretamos como sin cabecera
            tiene_cabecera = False
            if not sin_cabecera_flag:
                primer_val = primera_fila[0].strip().upper()
                if not primer_val.isdigit() and ('NRO' in primer_val or 'ID' in primer_val or 'EXPEDIENTE' in primer_val):
                    tiene_cabecera = True

            mapa_columnas = {}
            if tiene_cabecera:
                self.stdout.write("Encabezados detectados en la primera fila.")
                cabecera_limpia = [str(c).strip().upper().replace('.', '').replace(' ', '_') for c in primera_fila]
                # Mapear columnas según ALIAS
                for campo, aliases in self.ALIAS.items():
                    for alias in aliases:
                        if alias in cabecera_limpia:
                            mapa_columnas[campo] = cabecera_limpia.index(alias)
                            break
            else:
                self.stdout.write("Interpretando archivo por posición fija de columnas (sin encabezado).")
                for i, campo in enumerate(self.COLUMNAS_POSICIONALES):
                    mapa_columnas[campo] = i

            # Función para extraer valor según nombre de campo
            def get_val_fila(fila, campo):
                idx = mapa_columnas.get(campo)
                if idx is not None and idx < len(fila):
                    return fila[idx]
                return None

            # Procesar filas
            creados = 0
            actualizados = 0
            errores = 0
            batch = []
            batch_size = 500
            total_procesadas = 0

            # Si la primera fila eran datos, la agregamos al primer lote
            if not tiene_cabecera:
                batch.append(primera_fila)

            def procesar_lote(lote_filas):
                nonlocal creados, actualizados, errores
                with transaction.atomic():
                    for fila in lote_filas:
                        try:
                            nro = self._int(get_val_fila(fila, 'nro'))
                            ano = self._int(get_val_fila(fila, 'ano'))

                            if nro is None or ano is None:
                                errores += 1
                                continue

                            # Identificador canónico de expediente
                            expediente_val = self._str(get_val_fila(fila, 'expediente'))
                            numero_val = self._int(get_val_fila(fila, 'numero'))
                            if not expediente_val and numero_val and ano:
                                expediente_val = f"{ano}-{numero_val:03d}-1"

                            defaults = {
                                'id_origen': self._int(get_val_fila(fila, 'id_origen')),
                                'origen': self._str(get_val_fila(fila, 'origen')),
                                'clave': self._int(get_val_fila(fila, 'clave')),
                                'nombre_archivo': self._str(get_val_fila(fila, 'nombre_archivo')),
                                'fecha': self._dt(get_val_fila(fila, 'fecha')),
                                'usuario': self._str(get_val_fila(fila, 'usuario')),
                                'id_pase': self._int(get_val_fila(fila, 'id_pase')),
                                'id_cuerpo': self._int(get_val_fila(fila, 'id_cuerpo')),
                                'numero_pase': self._int(get_val_fila(fila, 'numero_pase')),
                                'id_expediente': self._int(get_val_fila(fila, 'id_expediente')),
                                'id_tipo_expediente': self._int(get_val_fila(fila, 'id_tipo_expediente')),
                                'tipo_expediente': self._str(get_val_fila(fila, 'tipo_expediente')),
                                'numero': numero_val,
                                'id_tipo_tramite': self._int(get_val_fila(fila, 'id_tipo_tramite')),
                                'tipo_tramite': self._str(get_val_fila(fila, 'tipo_tramite')),
                                'cuerpo_numero': self._int(get_val_fila(fila, 'cuerpo_numero')),
                                'id_tipo_pase': self._int(get_val_fila(fila, 'id_tipo_pase')),
                                'tipo_pase': self._str(get_val_fila(fila, 'tipo_pase')),
                                'id_responsable_emisor': self._str(get_val_fila(fila, 'id_responsable_emisor')),
                                'responsable_emisor': self._str(get_val_fila(fila, 'responsable_emisor')),
                                'id_area_destino': self._int(get_val_fila(fila, 'id_area_destino')),
                                'area_destino': self._str(get_val_fila(fila, 'area_destino')),
                                'fecha_realizacion': self._dt(get_val_fila(fila, 'fecha_realizacion')),
                                'fecha_recepcion': self._dt(get_val_fila(fila, 'fecha_recepcion')),
                                'fecha_registro': self._dt(get_val_fila(fila, 'fecha_registro')),
                                'fecha_actualizacion': self._dt(get_val_fila(fila, 'fecha_actualizacion')),
                                'id_responsable_receptor': self._str(get_val_fila(fila, 'id_responsable_receptor')),
                                'responsable_receptor': self._str(get_val_fila(fila, 'responsable_receptor')),
                                'observaciones': self._str(get_val_fila(fila, 'observaciones')),
                                'folios': self._int(get_val_fila(fila, 'folios')),
                                'id_operador': self._str(get_val_fila(fila, 'id_operador')),
                                'operador': self._str(get_val_fila(fila, 'operador')),
                                'fecha_inicio': self._dt(get_val_fila(fila, 'fecha_inicio')),
                                'area_iniciadora': self._str(get_val_fila(fila, 'area_iniciadora')),
                                'responsable_iniciador': self._str(get_val_fila(fila, 'responsable_iniciador')),
                                'expediente': expediente_val,
                            }

                            obj, created = Expediente.objects.update_or_create(
                                nro=nro,
                                ano=ano,
                                defaults=defaults
                            )

                            if created:
                                creados += 1
                            else:
                                actualizados += 1
                        except Exception as exc:
                            errores += 1

            for fila in reader:
                if not fila or not any(fila):
                    continue
                batch.append(fila)
                if len(batch) >= batch_size:
                    procesar_lote(batch)
                    total_procesadas += len(batch)
                    self.stdout.write(f"Procesadas {total_procesadas} filas...")
                    batch = []

            if batch:
                procesar_lote(batch)
                total_procesadas += len(batch)

        self.stdout.write(self.style.SUCCESS("--- RESUMEN DE IMPORTACIÓN CSV ---"))
        self.stdout.write(self.style.SUCCESS(f"Total filas procesadas: {total_procesadas}"))
        self.stdout.write(self.style.SUCCESS(f"Registros creados:       {creados}"))
        self.stdout.write(self.style.SUCCESS(f"Registros actualizados:  {actualizados}"))
        if errores > 0:
            self.stdout.write(self.style.WARNING(f"Filas con error u omitidas: {errores}"))
        else:
            self.stdout.write(self.style.SUCCESS("Errores: 0"))

