import os
import re
import copy
import zipfile
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from expedientes.models import Expediente


class Command(BaseCommand):
    help = 'Importa automáticamente todos los reportes anuales (2012 a 2026) con reconstrucción de Área Destino y adjuntos.'

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
        'numero': ['NUMERO_EXPEDIENTE', 'NUMERO', 'NRO_EXPEDIENTE_NUMERO'],
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
        parser.add_argument(
            '--carpeta',
            type=str,
            default='reportes',
            help='Carpeta donde se encuentran los archivos .xlsx (por defecto: reportes)'
        )
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Vaciar la tabla de expedientes antes de importar para asegurar una carga limpia sin duplicados.'
        )

    @staticmethod
    def _normalizar(texto: str) -> str:
        if not texto:
            return ''
        texto = str(texto).lower().strip()
        texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
        texto = texto.replace('.', '').replace(',', '')
        texto = re.sub(r'\s+', ' ', texto).strip()
        return texto

    @staticmethod
    def _str(val, max_len=None):
        if val is None:
            return None
        texto = str(val).strip()
        if not texto or texto.lower() in ('null', 'none', 'nan', '<vacío>', '<vacio>'):
            return None
        if max_len and len(texto) > max_len:
            texto = texto[:max_len]
        return texto

    @classmethod
    def _extraer_usuario(cls, raw_a):
        if not raw_a:
            return None
        m = re.search(r'Usuario:\s*([^-]+)', str(raw_a), re.IGNORECASE)
        if m:
            return cls._str(m.group(1), 50)
        return cls._str(raw_a, 50)

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
                    v = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                    val = None
                    if v is not None and v.text is not None:
                        val = shared_strings[int(v.text)] if c.get('t') == 's' else v.text
                    if nombre_col:
                        row_dict[nombre_col] = val
                    row_dict[f'__RAW_{letters}'] = val
                if row_dict:
                    datos.append(row_dict)
            return datos

    def calcular_campos_derivados(self, exp_obj):
        """Calcula los campos derivados necesarios para el motor de búsqueda y localización."""
        nombre = exp_obj.nombre_archivo or ''
        nombre = nombre.strip()

        exp_obj.tiene_adjunto = bool(nombre)
        exp_obj.secuencial = ''
        exp_obj.fecha_nombre = None
        exp_obj.tipo_nombre = 'vacio'

        if exp_obj.tiene_adjunto:
            patron_sistema = re.search(r'_(\d{8})_\d{6}_(\d{6})\.pdf$', nombre, re.IGNORECASE)
            if patron_sistema:
                exp_obj.tipo_nombre = 'sistema'
                exp_obj.secuencial = patron_sistema.group(2)
                try:
                    exp_obj.fecha_nombre = datetime.strptime(patron_sistema.group(1), '%m%d%Y').date()
                except ValueError:
                    exp_obj.fecha_nombre = None
            else:
                extensiones = ('.pdf', '.jpg', '.jpeg', '.png', '.zip', '.tif', '.tiff')
                if any(nombre.lower().endswith(ext) for ext in extensiones):
                    base, _ = os.path.splitext(nombre)
                    if re.match(r'^(IMAG\d+|IMG_\d+|Scan\d+|\d+)$', base, re.IGNORECASE):
                        exp_obj.tipo_nombre = 'generico'
                    else:
                        exp_obj.tipo_nombre = 'persona'
                else:
                    exp_obj.tipo_nombre = 'generico'

        exp_obj.nombre_normalizado = (self._normalizar(nombre) or '')[:255]
        exp_obj.secuencial = (exp_obj.secuencial or '')[:20]
        exp_obj.ubicado = exp_obj.ubicado or ''
        exp_obj.ruta = exp_obj.ruta or ''

        # Normalización del expediente canónico
        exp_val = exp_obj.expediente or ''
        if not exp_val and exp_obj.numero and exp_obj.ano:
            exp_val = f"{exp_obj.ano}-{exp_obj.numero:03d}-1"

        if ' 00:00:00' in exp_val and exp_obj.numero and exp_obj.ano:
            exp_obj.expediente_normalizado = f"{exp_obj.ano}-{exp_obj.numero:03d}-1"[:50]
        else:
            exp_obj.expediente_normalizado = (exp_val.strip() or '')[:50]

    def handle(self, *args, **options):
        carpeta = options['carpeta']
        limpiar = options['limpiar']

        if not os.path.exists(carpeta):
            self.stderr.write(self.style.ERROR(f"La carpeta '{carpeta}' no existe."))
            return

        if limpiar:
            self.stdout.write(self.style.WARNING("Vaciando tabla de expedientes para carga limpia..."))
            Expediente.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Tabla vaciada."))

        # ---------------------------------------------------------
        # FASE 1: Construcción de mapa de destinos y receptores
        # desde el reporte de adjuntos (EXPEDIENTES LISTADO ADJUNTOS)
        # ---------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING("\n[1/3] Cargando mapeos de destinos y funcionarios..."))
        ruta_adjuntos = os.path.join(carpeta, 'EXPEDIENTES LISTADO ADJUNTOS.xlsx')
        if not os.path.exists(ruta_adjuntos):
            # Alternativa en la raiz
            ruta_adjuntos = 'EXPEDIENTES LISTADO ADJUNTOS.xlsx'

        mapa_id_pase = {}
        mapa_receptores = {}
        receptor_top_area = {}

        if os.path.exists(ruta_adjuntos):
            filas_adj = self.leer_filas_xlsx(ruta_adjuntos)
            for r in filas_adj:
                id_p = self._int(self.get_val(r, 'id_pase'))
                dest = self._str(self.get_val(r, 'area_destino'))
                id_dest = self._int(self.get_val(r, 'id_area_destino'))
                rec = self._str(self.get_val(r, 'responsable_receptor'))

                if id_p and dest:
                    mapa_id_pase[id_p] = (id_dest, dest)

                if rec and dest:
                    rec_norm = self._normalizar(rec)
                    mapa_receptores.setdefault(rec_norm, {})
                    mapa_receptores[rec_norm][dest] = mapa_receptores[rec_norm].get(dest, 0) + 1

            for rec_norm, dests in mapa_receptores.items():
                area_predominante = max(dests.items(), key=lambda item: item[1])[0]
                receptor_top_area[rec_norm] = area_predominante

            self.stdout.write(self.style.SUCCESS(
                f"   [OK] {len(mapa_id_pase):,} pases con destino exacto indexados.\n"
                f"   [OK] {len(receptor_top_area)} funcionarios receptores mapeados a sus areas."
            ))
        else:
            self.stdout.write(self.style.WARNING("   [!] No se encontro EXPEDIENTES LISTADO ADJUNTOS.xlsx. Se usara solo secuencia."))

        # ---------------------------------------------------------
        # FASE 2: Lectura de reportes anuales (2012 a 2026),
        # vinculación de adjuntos desfasados y reconstrucción de Área Destino
        # ---------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING("\n[2/3] Procesando reportes anuales (2012 a 2026)..."))
        archivos_anuales = []
        for anio in range(2012, 2027):
            nombre = f"{anio}.xlsx"
            ruta = os.path.join(carpeta, nombre)
            if os.path.exists(ruta):
                archivos_anuales.append((anio, ruta))

        todos_los_objetos = []
        expedientes_pases = {}  # exp_key -> [obj, obj, ...]

        cont_dest_exacto = 0
        cont_dest_secuencia = 0
        cont_dest_receptor = 0

        for anio, ruta in archivos_anuales:
            self.stdout.write(f"   -> Leyendo {anio} ({os.path.basename(ruta)})...")
            filas = self.leer_filas_xlsx(ruta)
            padre_actual = None

            for row in filas:
                raw_a = row.get('__RAW_A')
                # Detección de subfila de adjunto desfasado (exportación multi-línea)
                if str(raw_a).startswith('_____Usuario:'):
                    if padre_actual:
                        nombre_adjunto = self._str(row.get('__RAW_B'), 255)
                        fecha_adjunto = self._dt(row.get('__RAW_C'))
                        usuario_adjunto = self._extraer_usuario(raw_a)
                        # Si el pase padre no tenía archivo en su columna principal, se lo asignamos
                        if not padre_actual.nombre_archivo and nombre_adjunto:
                            padre_actual.nombre_archivo = nombre_adjunto
                            padre_actual.fecha = fecha_adjunto or padre_actual.fecha
                            padre_actual.usuario = usuario_adjunto
                        elif nombre_adjunto:
                            # Si es un adjunto secundario del mismo pase, clonamos el pase con este adjunto
                            hijo = copy.copy(padre_actual)
                            hijo.pk = None
                            hijo.nombre_archivo = nombre_adjunto
                            hijo.fecha = fecha_adjunto or padre_actual.fecha
                            hijo.usuario = usuario_adjunto
                            todos_los_objetos.append(hijo)
                            exp_key = f"{hijo.ano}-{hijo.numero}"
                            expedientes_pases.setdefault(exp_key, []).append(hijo)
                    continue

                id_pase = self._int(self.get_val(row, 'id_pase'))
                numero = self._int(self.get_val(row, 'numero'))
                ano_fila = self._int(self.get_val(row, 'ano')) or anio
                nro = self._int(self.get_val(row, 'nro'))

                # Omitir filas sin identidad de trámite
                if not numero and not id_pase and not nro:
                    continue

                expediente_val = self._str(self.get_val(row, 'expediente'), 50)
                if not expediente_val and numero and ano_fila:
                    expediente_val = f"{ano_fila}-{numero:03d}-1"

                area_dest = self._str(self.get_val(row, 'area_destino'), 150)
                id_area_dest = self._int(self.get_val(row, 'id_area_destino'))

                # Método 1: Cruce exacto por IdPase
                if not area_dest and id_pase and id_pase in mapa_id_pase:
                    id_area_dest, area_dest = mapa_id_pase[id_pase]
                    cont_dest_exacto += 1

                exp = Expediente(
                    nro=nro,
                    ano=ano_fila,
                    id_origen=self._int(self.get_val(row, 'id_origen')),
                    origen=self._str(self.get_val(row, 'origen'), 50),
                    clave=self._int(self.get_val(row, 'clave')),
                    nombre_archivo=self._str(self.get_val(row, 'nombre_archivo'), 255),
                    fecha=self._dt(self.get_val(row, 'fecha')),
                    usuario=self._str(self.get_val(row, 'usuario'), 50),
                    id_pase=id_pase,
                    id_cuerpo=self._int(self.get_val(row, 'id_cuerpo')),
                    numero_pase=self._int(self.get_val(row, 'numero_pase')),
                    id_expediente=self._int(self.get_val(row, 'id_expediente')),
                    id_tipo_expediente=self._int(self.get_val(row, 'id_tipo_expediente')),
                    tipo_expediente=self._str(self.get_val(row, 'tipo_expediente'), 100),
                    numero=numero,
                    id_tipo_tramite=self._int(self.get_val(row, 'id_tipo_tramite')),
                    tipo_tramite=self._str(self.get_val(row, 'tipo_tramite'), 150),
                    cuerpo_numero=self._int(self.get_val(row, 'cuerpo_numero')) or 1,
                    id_tipo_pase=self._int(self.get_val(row, 'id_tipo_pase')),
                    tipo_pase=self._str(self.get_val(row, 'tipo_pase'), 100),
                    id_responsable_emisor=self._str(self.get_val(row, 'id_responsable_emisor'), 20),
                    responsable_emisor=self._str(self.get_val(row, 'responsable_emisor'), 150),
                    id_area_destino=id_area_dest,
                    area_destino=self._str(area_dest, 150),
                    fecha_realizacion=self._dt(self.get_val(row, 'fecha_realizacion')),
                    fecha_recepcion=self._dt(self.get_val(row, 'fecha_recepcion')),
                    fecha_registro=self._dt(self.get_val(row, 'fecha_registro')),
                    fecha_actualizacion=self._dt(self.get_val(row, 'fecha_actualizacion')),
                    id_responsable_receptor=self._str(self.get_val(row, 'id_responsable_receptor'), 20),
                    responsable_receptor=self._str(self.get_val(row, 'responsable_receptor'), 150),
                    observaciones=self._str(self.get_val(row, 'observaciones')),
                    folios=self._int(self.get_val(row, 'folios')),
                    id_operador=self._str(self.get_val(row, 'id_operador'), 20),
                    operador=self._str(self.get_val(row, 'operador'), 150),
                    fecha_inicio=self._dt(self.get_val(row, 'fecha_inicio')),
                    area_iniciadora=self._str(self.get_val(row, 'area_iniciadora'), 150),
                    responsable_iniciador=self._str(self.get_val(row, 'responsable_iniciador'), 150),
                    expediente=self._str(expediente_val, 50),
                )
                todos_los_objetos.append(exp)
                exp_key = f"{ano_fila}-{numero}"
                expedientes_pases.setdefault(exp_key, []).append(exp)
                padre_actual = exp

        # ---------------------------------------------------------
        # FASE 2.1: Propagación de Área Destino entre registros del mismo IdPase
        # ---------------------------------------------------------
        self.stdout.write("   -> Unificando areas de destino en pases con multiples adjuntos...")
        destinos_por_id_pase = {}
        for obj in todos_los_objetos:
            if obj.id_pase and obj.area_destino:
                destinos_por_id_pase[obj.id_pase] = (obj.id_area_destino, obj.area_destino)

        for obj in todos_los_objetos:
            if obj.id_pase and not obj.area_destino and obj.id_pase in destinos_por_id_pase:
                obj.id_area_destino, obj.area_destino = destinos_por_id_pase[obj.id_pase]

        # ---------------------------------------------------------
        # FASE 2.2: Reconstrucción por Secuencia Cronológica (flujo del trámite)
        # ---------------------------------------------------------
        self.stdout.write("   -> Reconstruyendo areas de destino por secuencia cronologica...")
        for exp_key, pases in expedientes_pases.items():
            # Ordenar por número de pase
            pases.sort(key=lambda x: (x.numero_pase if x.numero_pase is not None else 0))
            for i, p_actual in enumerate(pases):
                if not p_actual.area_destino:
                    # Buscar el siguiente pase con número de pase estrictamente mayor
                    num_actual = p_actual.numero_pase or 0
                    for p_sig in pases[i + 1:]:
                        num_sig = p_sig.numero_pase or 0
                        if num_sig > num_actual and p_sig.area_iniciadora:
                            p_actual.area_destino = self._str(p_sig.area_iniciadora, 150)
                            cont_dest_secuencia += 1
                            break

        # ---------------------------------------------------------
        # FASE 2.3: Reconstrucción por Funcionario Receptor conocido
        # ---------------------------------------------------------
        self.stdout.write("   -> Asignando areas por funcionario receptor conocido...")
        for exp in todos_los_objetos:
            if not exp.area_destino and exp.responsable_receptor:
                rec_norm = self._normalizar(exp.responsable_receptor)
                if rec_norm in receptor_top_area:
                    exp.area_destino = self._str(receptor_top_area[rec_norm], 150)
                    cont_dest_receptor += 1

        # ---------------------------------------------------------
        # FASE 2.4: Propagación final a adjuntos del mismo pase que no tenían destino
        # ---------------------------------------------------------
        pases_con_destino = {}
        for exp in todos_los_objetos:
            if exp.area_destino:
                clave_pase = (exp.expediente or f"{exp.ano}-{exp.numero}", exp.numero_pase)
                if clave_pase not in pases_con_destino:
                    pases_con_destino[clave_pase] = exp.area_destino

        for exp in todos_los_objetos:
            if not exp.area_destino:
                clave_pase = (exp.expediente or f"{exp.ano}-{exp.numero}", exp.numero_pase)
                if clave_pase in pases_con_destino:
                    exp.area_destino = pases_con_destino[clave_pase]

            # Calcular campos derivados de búsqueda
            self.calcular_campos_derivados(exp)

        # ---------------------------------------------------------
        # FASE 3: Inserción en Base de Datos (bulk_create optimizado)
        # ---------------------------------------------------------
        total_pases = len(todos_los_objetos)
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n[3/3] Guardando {total_pases:,} registros en la base de datos..."))

        batch_size = 250  # Lote seguro para respetar max_allowed_packet en MySQL
        guardados = 0
        for i in range(0, total_pases, batch_size):
            lote = todos_los_objetos[i:i + batch_size]
            Expediente.objects.bulk_create(lote)
            guardados += len(lote)
            if guardados % 5000 < batch_size or guardados >= total_pases:
                porcentaje = (guardados / total_pases) * 100
                self.stdout.write(f"   -> {guardados:,} / {total_pases:,} guardados ({porcentaje:.1f}%)...")

        total_con_destino = cont_dest_exacto + cont_dest_secuencia + cont_dest_receptor
        total_adjuntos = sum(1 for e in todos_los_objetos if e.tiene_adjunto)

        self.stdout.write(self.style.SUCCESS("\n========================================================"))
        self.stdout.write(self.style.SUCCESS("  IMPORTACION Y RECONSTRUCCION COMPLETADA CON EXITO!"))
        self.stdout.write(self.style.SUCCESS(f"  * Total registros importados: {total_pases:,}"))
        self.stdout.write(self.style.SUCCESS(f"  * Total pases con adjunto: {total_adjuntos:,}"))
        self.stdout.write(self.style.SUCCESS(f"  * Area Destino recuperada: {total_con_destino:,} ({(total_con_destino / total_pases) * 100:.1f}%)"))
        self.stdout.write(f"    - Por cruce exacto IdPase: {cont_dest_exacto:,}")
        self.stdout.write(f"    - Por flujo cronologico entre pases: {cont_dest_secuencia:,}")
        self.stdout.write(f"    - Por funcionario receptor conocido: {cont_dest_receptor:,}")
        self.stdout.write(self.style.SUCCESS("========================================================\n"))
