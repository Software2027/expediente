import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from expedientes.models import Expediente


class Command(BaseCommand):
    help = 'Importa expedientes y adjuntos para un año específico desde un archivo Excel'

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
        parser.add_argument('excel_path', type=str, help='Ruta completa o relativa al archivo Excel (.xlsx)')
        parser.add_argument('--anio', type=int, required=True, help='Año que se está importando (ej. 2024)')

    @staticmethod
    def _str(val):
        if val is None:
            return None
        texto = str(val).strip()
        if not texto or texto.lower() in ('null', 'none', 'nan', '<vacío>'):
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

    def get_val(self, row, campo):
        aliases = self.ALIAS.get(campo, [campo.upper()])
        for alias in aliases:
            if alias in row and row[alias] is not None:
                return row[alias]
        return None

    def leer_filas_xlsx(self, ruta_archivo):
        def col_to_num(col_str):
            num = 0
            for c in col_str:
                num = num * 26 + (ord(c.upper()) - ord('A')) + 1
            return num - 1

        with zipfile.ZipFile(ruta_archivo, 'r') as z:
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                for si in tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                    text = ''.join(t.text for t in si.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t') if t.text)
                    shared_strings.append(text)

            sheet_path = 'xl/worksheets/sheet1.xml'
            sheet_tree = ET.fromstring(z.read(sheet_path))
            rows = sheet_tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')
            if not rows:
                return []

            headers = {}
            for c in rows[0].findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                ref = c.get('r', '')
                letters = ''.join([ch for ch in ref if ch.isalpha()])
                col_idx = col_to_num(letters)
                v = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                val = ''
                if v is not None and v.text is not None:
                    val = shared_strings[int(v.text)] if c.get('t') == 's' else v.text
                val_limpio = str(val).strip().replace('.', '').replace(' ', '_').upper()
                headers[col_idx] = val_limpio

            datos = []
            for r in rows[1:]:
                row_dict = {}
                for c in r.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                    ref = c.get('r', '')
                    letters = ''.join([ch for ch in ref if ch.isalpha()])
                    col_idx = col_to_num(letters)
                    nombre_col = headers.get(col_idx)
                    if nombre_col:
                        v = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                        val = None
                        if v is not None and v.text is not None:
                            val = shared_strings[int(v.text)] if c.get('t') == 's' else v.text
                        row_dict[nombre_col] = val
                if row_dict:
                    datos.append(row_dict)
            return datos

    def handle(self, *args, **options):
        excel_path = options['excel_path']
        anio_objetivo = options['anio']

        if not os.path.exists(excel_path):
            self.stderr.write(self.style.ERROR(f"El archivo no existe: {excel_path}"))
            return

        self.stdout.write(self.style.NOTICE(f"Importando año {anio_objetivo} desde: {excel_path}..."))

        filas = self.leer_filas_xlsx(excel_path)
        total_filas = len(filas)
        self.stdout.write(f"Total de filas leídas: {total_filas}")

        creados = 0
        actualizados = 0
        errores = 0
        omitidos_por_anio = 0
        batch_size = 500

        for i in range(0, total_filas, batch_size):
            batch = filas[i:i + batch_size]
            with transaction.atomic():
                for row in batch:
                    try:
                        nro = self._int(self.get_val(row, 'nro'))
                        ano_fila = self._int(self.get_val(row, 'ano'))

                        if ano_fila is not None and ano_fila != anio_objetivo:
                            omitidos_por_anio += 1
                            continue

                        if nro is None:
                            errores += 1
                            continue

                        ano = anio_objetivo

                        expediente_val = self._str(self.get_val(row, 'expediente'))
                        numero_val = self._int(self.get_val(row, 'numero'))
                        if not expediente_val and numero_val and ano:
                            expediente_val = f"{ano}-{numero_val:03d}-1"

                        defaults = {
                            'id_origen': self._int(self.get_val(row, 'id_origen')),
                            'origen': self._str(self.get_val(row, 'origen')),
                            'clave': self._int(self.get_val(row, 'clave')),
                            'nombre_archivo': self._str(self.get_val(row, 'nombre_archivo')),
                            'fecha': self._dt(self.get_val(row, 'fecha')),
                            'usuario': self._str(self.get_val(row, 'usuario')),
                            'id_pase': self._int(self.get_val(row, 'id_pase')),
                            'id_cuerpo': self._int(self.get_val(row, 'id_cuerpo')),
                            'numero_pase': self._int(self.get_val(row, 'numero_pase')),
                            'id_expediente': self._int(self.get_val(row, 'id_expediente')),
                            'id_tipo_expediente': self._int(self.get_val(row, 'id_tipo_expediente')),
                            'tipo_expediente': self._str(self.get_val(row, 'tipo_expediente')),
                            'numero': numero_val,
                            'id_tipo_tramite': self._int(self.get_val(row, 'id_tipo_tramite')),
                            'tipo_tramite': self._str(self.get_val(row, 'tipo_tramite')),
                            'cuerpo_numero': self._int(self.get_val(row, 'cuerpo_numero')),
                            'id_tipo_pase': self._int(self.get_val(row, 'id_tipo_pase')),
                            'tipo_pase': self._str(self.get_val(row, 'tipo_pase')),
                            'id_responsable_emisor': self._str(self.get_val(row, 'id_responsable_emisor')),
                            'responsable_emisor': self._str(self.get_val(row, 'responsable_emisor')),
                            'id_area_destino': self._int(self.get_val(row, 'id_area_destino')),
                            'area_destino': self._str(self.get_val(row, 'area_destino')),
                            'fecha_realizacion': self._dt(self.get_val(row, 'fecha_realizacion')),
                            'fecha_recepcion': self._dt(self.get_val(row, 'fecha_recepcion')),
                            'fecha_registro': self._dt(self.get_val(row, 'fecha_registro')),
                            'fecha_actualizacion': self._dt(self.get_val(row, 'fecha_actualizacion')),
                            'id_responsable_receptor': self._str(self.get_val(row, 'id_responsable_receptor')),
                            'responsable_receptor': self._str(self.get_val(row, 'responsable_receptor')),
                            'observaciones': self._str(self.get_val(row, 'observaciones')),
                            'folios': self._int(self.get_val(row, 'folios')),
                            'id_operador': self._str(self.get_val(row, 'id_operador')),
                            'operador': self._str(self.get_val(row, 'operador')),
                            'fecha_inicio': self._dt(self.get_val(row, 'fecha_inicio')),
                            'area_iniciadora': self._str(self.get_val(row, 'area_iniciadora')),
                            'responsable_iniciador': self._str(self.get_val(row, 'responsable_iniciador')),
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
                    except Exception:
                        errores += 1

            procesadas = min(i + batch_size, total_filas)
            self.stdout.write(f"Procesadas {procesadas}/{total_filas} filas...")

        self.stdout.write(self.style.SUCCESS(f"Año {anio_objetivo}: {creados} creados, {actualizados} actualizados"))
        if omitidos_por_anio > 0 or errores > 0:
            self.stdout.write(self.style.WARNING(f"Detalle: {omitidos_por_anio} omitidas por año distinto, {errores} errores."))
