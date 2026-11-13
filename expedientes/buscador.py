import re
import unicodedata
from datetime import datetime, time
from collections import Counter
from django.utils import timezone
from django.db.models import Q, Case, When, Value, IntegerField, Count
from django.db.models.functions import Coalesce
from .models import Expediente


def normalizar(texto: str) -> str:
    """
    Normaliza texto para búsquedas insensibles a mayúsculas, tildes y puntuación común:
    - Convierte a minúsculas y elimina espacios sobrantes en extremos.
    - Descompone caracteres Unicode (NFD) y elimina marcas diacríticas (acentos/tildes).
    - Elimina puntos y comas.
    - Colapsa espacios en blanco repetidos en un solo espacio.
    """
    if not texto:
        return ''
    texto = str(texto).lower().strip()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    texto = texto.replace('.', '').replace(',', '')
    texto = re.sub(r'\s+', ' ', texto)
    return texto


def buscar(q=None, ano=None, tipo=None, area=None, desde=None, hasta=None, nro_exp=None):
    """
    Buscador inteligente de expedientes y adjuntos.
    Detecta automáticamente patrones comunes en el término de búsqueda `q`
    y los combina con búsqueda de texto completo y filtros opcionales (año, tipo, área, fechas, nro_exp).

    Prioriza resultados colocando primero las coincidencias exactas o al inicio
    del nombre de archivo o expediente.
    """
    qs = Expediente.objects.all()

    def _aplicar_filtro_nro_exp(query_set, valor):
        if not valor:
            return query_set
        val_str = str(valor).strip()
        if not val_str:
            return query_set
        if val_str.isdigit():
            num_val = int(val_str)
            return query_set.filter(
                Q(numero=num_val) | Q(expediente__icontains=val_str) | Q(expediente_normalizado__icontains=val_str)
            )
        return query_set.filter(
            Q(expediente__icontains=val_str) | Q(expediente_normalizado__icontains=val_str)
        )

    def _parsear_fecha_rango(desde_val, hasta_val):
        desde_dt = None
        if desde_val:
            try:
                d = datetime.strptime(str(desde_val).strip(), '%Y-%m-%d').date()
                dt_naive = datetime.combine(d, time.min)
                desde_dt = timezone.make_aware(dt_naive) if timezone.is_naive(dt_naive) else dt_naive
            except (ValueError, TypeError):
                desde_dt = None

        hasta_dt = None
        if hasta_val:
            try:
                h = datetime.strptime(str(hasta_val).strip(), '%Y-%m-%d').date()
                dt_naive = datetime.combine(h, time.max)
                hasta_dt = timezone.make_aware(dt_naive) if timezone.is_naive(dt_naive) else dt_naive
            except (ValueError, TypeError):
                hasta_dt = None

        return desde_dt, hasta_dt

    def _aplicar_filtros_comunes(query_set):
        if nro_exp:
            query_set = _aplicar_filtro_nro_exp(query_set, nro_exp)
        if ano:
            query_set = query_set.filter(ano=ano)
        if tipo:
            query_set = query_set.filter(tipo_expediente__icontains=tipo)
        if area:
            query_set = query_set.filter(Q(area_destino__icontains=area) | Q(area_iniciadora__icontains=area))

        desde_dt, hasta_dt = _parsear_fecha_rango(desde, hasta)
        if desde_dt or hasta_dt:
            query_set = query_set.annotate(
                fecha_efectiva=Coalesce('fecha_realizacion', 'fecha', 'fecha_recepcion', 'fecha_registro', 'fecha_inicio')
            )
            if desde_dt:
                query_set = query_set.filter(fecha_efectiva__gte=desde_dt)
            if hasta_dt:
                query_set = query_set.filter(fecha_efectiva__lte=hasta_dt)

        return query_set

    # Si no hay término de búsqueda, aplica solo filtros opcionales ordenados por fecha
    if not q or not str(q).strip():
        qs = _aplicar_filtros_comunes(qs)
        return qs.order_by('-ano', '-numero', '-fecha_realizacion', '-fecha')

    termino = str(q).strip()
    q_norm = normalizar(termino)

    condiciones_dinamicas = Q()

    # a) Detección de formato canónico de expediente: AAAA-NNN-C (ej. "2024-1836-1")
    if re.match(r'^\d{4}-\d+-\d+$', termino):
        condiciones_dinamicas |= Q(expediente_normalizado__icontains=termino)

    # b) Detección de secuencial numérico de 6 dígitos (adjuntos del sistema, ej. "041877")
    if re.match(r'^\d{6}$', termino):
        condiciones_dinamicas |= Q(secuencial=termino)

    # c) Detección de par "número año" (ej. "1836 2024")
    match_num_ano = re.match(r'^(\d+)\s+(\d{4})$', termino)
    if match_num_ano:
        numero = int(match_num_ano.group(1))
        anio = int(match_num_ano.group(2))
        condiciones_dinamicas |= Q(numero=numero, ano=anio)

    # d) Detección de número entero suelto (busca en número de expediente, Nro. de fila o clave)
    if re.match(r'^\d+$', termino):
        val_int = int(termino)
        condiciones_dinamicas |= (Q(numero=val_int) | Q(nro=val_int) | Q(clave=val_int))

    # e) Detección de nombre de archivo con extensión (ej. "DELGADO.zip", "archivo.pdf")
    if re.search(r'\.(pdf|jpg|jpeg|png|zip|tif|tiff)$', termino, re.IGNORECASE):
        condiciones_dinamicas |= Q(nombre_normalizado__icontains=q_norm)

    # f) Detección de fecha en formato DD/MM/AAAA o DD-MM-AAAA (ej. "15/11/2024")
    match_fecha = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$', termino)
    if match_fecha:
        d, m, y = match_fecha.groups()
        fecha_iso = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        condiciones_dinamicas |= Q(fecha__date=fecha_iso)

    # g) Búsqueda amplia por texto (coincidencia general en personas, áreas, operador y observaciones)
    condiciones_dinamicas |= (
        Q(nombre_normalizado__icontains=q_norm)
        | Q(responsable_iniciador__icontains=termino)
        | Q(responsable_emisor__icontains=termino)
        | Q(responsable_receptor__icontains=termino)
        | Q(operador__icontains=termino)
        | Q(area_destino__icontains=termino)
        | Q(tipo_expediente__icontains=termino)
        | Q(tipo_tramite__icontains=termino)
        | Q(observaciones__icontains=termino)
        | Q(expediente_normalizado__icontains=q_norm)
    )

    qs = qs.filter(condiciones_dinamicas)

    # Aplicar filtros complementarios opcionales
    qs = _aplicar_filtros_comunes(qs)

    # Priorización de relevancia:
    # Prioridad 0: Coincidencia exacta en nombre normalizado o expediente
    # Prioridad 1: Coincidencia al inicio en nombre normalizado o expediente
    # Prioridad 2: Coincidencia en cualquier parte del nombre normalizado
    # Prioridad 3: Resto de coincidencias (personas, observaciones, áreas, etc.)
    qs = qs.annotate(
        prioridad=Case(
            When(
                Q(nombre_normalizado__iexact=q_norm) | Q(expediente_normalizado__iexact=termino),
                then=Value(0)
            ),
            When(
                Q(nombre_normalizado__istartswith=q_norm) | Q(expediente_normalizado__istartswith=termino),
                then=Value(1)
            ),
            When(
                Q(nombre_normalizado__icontains=q_norm),
                then=Value(2)
            ),
            default=Value(3),
            output_field=IntegerField()
        )
    ).order_by('prioridad', '-fecha')

    return qs


def estadisticas_por_anio():
    """
    Retorna una lista de diccionarios con el resumen de expedientes por año:
    [{'ano': 2025, 'total': 200, 'con_adjunto': 150, 'sin_adjunto': 50, 'porcentaje': 75.0}, ...]
    """
    qs = Expediente.objects.values('ano').annotate(
        total=Count('id'),
        con_adjunto=Count('id', filter=Q(tiene_adjunto=True)),
        sin_adjunto=Count('id', filter=Q(tiene_adjunto=False))
    ).order_by('-ano')

    resumen = []
    for fila in qs:
        total = fila['total']
        con_adjunto = fila['con_adjunto']
        sin_adjunto = fila['sin_adjunto']
        porcentaje = round((con_adjunto * 100.0 / total), 1) if total > 0 else 0.0

        resumen.append({
            'ano': fila['ano'],
            'total': total,
            'con_adjunto': con_adjunto,
            'sin_adjunto': sin_adjunto,
            'porcentaje': porcentaje,
        })

    return resumen


def pista_busqueda(expediente: Expediente) -> dict:
    """
    Determina la sugerencia y dato clave que el empleado debe copiar
    para localizar el archivo físico en el disco duro.
    """
    if not expediente:
        return {
            'texto': None,
            'tipo': 'vacio',
            'label': None,
            'ayuda': 'Sin adjunto digital'
        }

    tipo = expediente.tipo_nombre

    if tipo == 'sistema':
        return {
            'texto': expediente.secuencial,
            'tipo': 'secuencial',
            'label': 'Copiar secuencial',
            'ayuda': 'Buscá este número en el disco'
        }
    elif tipo == 'persona':
        return {
            'texto': expediente.nombre_archivo,
            'tipo': 'nombre',
            'label': 'Copiar nombre',
            'ayuda': 'Buscá este nombre en el disco'
        }
    elif tipo == 'generico':
        fecha_str = expediente.fecha.strftime('%d/%m/%Y') if expediente.fecha else 'sin fecha'
        return {
            'texto': None,
            'tipo': 'fecha',
            'label': None,
            'ayuda': f"Nombre genérico. Buscá por fecha: {fecha_str}"
        }
    else:  # 'vacio' o cualquier otro caso
        return {
            'texto': None,
            'tipo': 'vacio',
            'label': None,
            'ayuda': 'Sin adjunto digital'
        }


def resumen_resultados(resultados) -> dict:
    """
    Calcula el resumen de totales y tipos de adjunto para un QuerySet o lista de resultados.
    """
    conteo = Counter()
    total = 0
    con_adjunto = 0
    sin_adjunto = 0

    for exp in resultados:
        total += 1
        if exp.tiene_adjunto:
            con_adjunto += 1
        else:
            sin_adjunto += 1
        conteo[exp.tipo_nombre] += 1

    return {
        'total': total,
        'con_adjunto': con_adjunto,
        'sin_adjunto': sin_adjunto,
        'sistema': conteo['sistema'],
        'persona': conteo['persona'],
        'generico': conteo['generico'],
        'vacio': conteo['vacio'],
    }

