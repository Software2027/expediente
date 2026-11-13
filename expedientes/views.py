from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Expediente
from .buscador import buscar, pista_busqueda, resumen_resultados


@login_required
def buscador(request):
    """
    Vista principal del buscador de expedientes.
    Procesa los filtros de búsqueda por texto, año, tipo, área y rango de fechas.
    Implementa paginación eficiente de 25 registros por página preservando los filtros aplicados.
    """
    q = request.GET.get('q', '').strip()
    nro_exp = request.GET.get('nro_exp', '').strip() or None
    ano_raw = request.GET.get('ano', '').strip()
    tipo = request.GET.get('tipo', '').strip() or None
    area = request.GET.get('area', '').strip() or None
    desde = request.GET.get('desde', '').strip() or None
    hasta = request.GET.get('hasta', '').strip() or None
    por_pagina_raw = request.GET.get('por_pagina', '25').strip()

    # Tamaño de página seguro
    try:
        por_pagina = int(por_pagina_raw)
        if por_pagina not in (10, 25, 50, 100):
            por_pagina = 25
    except (ValueError, TypeError):
        por_pagina = 25

    # Conversión segura del parámetro año
    ano = None
    if ano_raw:
        try:
            ano = int(ano_raw)
        except (ValueError, TypeError):
            ano = None

    # Determinar si el usuario aplicó alguna búsqueda o filtro
    hay_busqueda = bool(q or nro_exp or ano is not None or tipo or area or desde or hasta)

    # Catálogos para los menús desplegables de filtrado
    anos_disponibles = (
        Expediente.objects.values_list('ano', flat=True)
        .exclude(ano__isnull=True)
        .distinct()
        .order_by('-ano')
    )

    tipos_disponibles = (
        Expediente.objects.values_list('tipo_expediente', flat=True)
        .exclude(tipo_expediente='')
        .exclude(tipo_expediente__isnull=True)
        .distinct()
        .order_by('tipo_expediente')
    )

    areas_dest = set(
        Expediente.objects.exclude(area_destino__isnull=True)
        .exclude(area_destino='')
        .exclude(area_destino='0.0')
        .values_list('area_destino', flat=True)
        .distinct()
    )
    areas_ini = set(
        Expediente.objects.exclude(area_iniciadora__isnull=True)
        .exclude(area_iniciadora='')
        .exclude(area_iniciadora='0.0')
        .values_list('area_iniciadora', flat=True)
        .distinct()
    )
    areas_disponibles = sorted(a for a in (areas_dest | areas_ini) if a and a != '0.0')

    # Parámetros GET limpios para mantener los filtros en los enlaces de paginación
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    params_url = query_params.urlencode()

    resultados_con_pista = []
    page_obj = None
    page_range = []
    total = 0
    resumen = None

    if hay_busqueda:
        # Ejecutar búsqueda mediante el motor inteligente
        resultados_qs = buscar(q=q, ano=ano, tipo=tipo, area=area, desde=desde, hasta=hasta, nro_exp=nro_exp)
        total = resultados_qs.count()

        # Resumen general del resultado de búsqueda
        if total <= 1000:
            resumen = resumen_resultados(resultados_qs)
        else:
            resumen = resumen_resultados(resultados_qs[:200])
    else:
        # Si no hay filtros, exploramos todos los expedientes ordenados cronológicamente
        resultados_qs = Expediente.objects.all().order_by('-ano', '-numero', '-fecha')
        total = resultados_qs.count()

    # Paginación configurable (25 por defecto, 10, 50 o 100)
    paginator = Paginator(resultados_qs, por_pagina)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.get_page(1)

    # Rango de páginas elipsado inteligente (ej: [1, 2, '…', 15, 16, 17, '…', 3798])
    page_range = paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)

    # Precalcular pistas solo para los registros visibles en la página actual
    resultados_con_pista = [
        {'exp': r, 'pista': pista_busqueda(r)} for r in page_obj
    ]

    context = {
        'q': q,
        'nro_exp': nro_exp,
        'ano': ano,
        'tipo': tipo,
        'area': area,
        'desde': desde,
        'hasta': hasta,
        'por_pagina': por_pagina,
        'hay_busqueda': hay_busqueda,
        'resultados': resultados_con_pista,
        'page_obj': page_obj,
        'page_range': page_range,
        'params_url': params_url,
        'total': total,
        'resumen': resumen,
        'anos_disponibles': anos_disponibles,
        'tipos_disponibles': tipos_disponibles,
        'areas_disponibles': areas_disponibles,
    }

    return render(request, 'expedientes/buscador.html', context)


@login_required
def detalle(request, pk):
    """
    Vista de detalle para un expediente específico.
    Permite consultar toda su información, el historial cronológico completo
    de pases/movimientos del expediente y actualizar su estado de ubicación en disco.
    """
    exp = get_object_or_404(Expediente, pk=pk)

    if request.method == 'POST':
        ubicado = request.POST.get('ubicado', '').strip()
        ruta = request.POST.get('ruta', '').strip()

        # Validación de estados permitidos
        if ubicado not in ('', 'OK', 'NO', 'DUDOSO'):
            ubicado = ''

        exp.ubicado = ubicado
        exp.ruta = ruta
        exp.fecha_busqueda = timezone.now() if ubicado else None
        exp.save(update_fields=['ubicado', 'ruta', 'fecha_busqueda'])

        messages.success(request, f'Expediente {exp.expediente or exp.nro} actualizado correctamente.')
        return redirect('expedientes:detalle', pk=pk)

    # Pista del expediente actual
    pista = pista_busqueda(exp)

    # Obtener el historial completo de pases y adjuntos vinculados a este mismo expediente
    criterios_historial = None
    if exp.id_expediente and exp.id_expediente > 0:
        criterios_historial = Expediente.objects.filter(id_expediente=exp.id_expediente)
    elif exp.expediente_normalizado:
        criterios_historial = Expediente.objects.filter(expediente_normalizado=exp.expediente_normalizado)
    elif exp.numero and exp.ano:
        criterios_historial = Expediente.objects.filter(numero=exp.numero, ano=exp.ano)

    if criterios_historial is not None:
        historial_pases = criterios_historial.order_by('numero_pase', 'fecha', 'id')
    else:
        historial_pases = Expediente.objects.filter(pk=exp.pk)

    historial_con_pista = [
        {'pase': p, 'pista': pista_busqueda(p)} for p in historial_pases
    ]

    total_movimientos = len(historial_con_pista)
    total_adjuntos_exp = sum(1 for item in historial_con_pista if item['pase'].tiene_adjunto)

    return render(request, 'expedientes/detalle.html', {
        'exp': exp,
        'pista': pista,
        'historial_pases': historial_con_pista,
        'total_movimientos': total_movimientos,
        'total_adjuntos_exp': total_adjuntos_exp,
    })


@login_required
def marcar_ubicado(request, pk):
    """
    Endpoint POST para actualizar el estado de ubicación física del archivo en disco.
    """
    if request.method != 'POST':
        return redirect('expedientes:detalle', pk=pk)

    exp = get_object_or_404(Expediente, pk=pk)
    ubicado = request.POST.get('ubicado', '').strip()
    ruta = request.POST.get('ruta', '').strip()

    # Validación estricta de opciones
    if ubicado not in ('', 'OK', 'NO', 'DUDOSO'):
        ubicado = ''

    exp.ubicado = ubicado
    exp.ruta = ruta
    exp.fecha_busqueda = timezone.now() if ubicado else None
    exp.save(update_fields=['ubicado', 'ruta', 'fecha_busqueda'])

    messages.success(request, f'Expediente {exp.expediente or exp.nro} actualizado.')
    return redirect('expedientes:detalle', pk=pk)

