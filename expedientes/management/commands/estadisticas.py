from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from expedientes.models import Expediente


class Command(BaseCommand):
    help = 'Muestra estadísticas de expedientes y adjuntos por año'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== ESTADÍSTICAS DE EXPEDIENTES POR AÑO ==="))

        estadisticas = Expediente.objects.values('ano').annotate(
            total=Count('id'),
            con_adjunto=Count('id', filter=Q(tiene_adjunto=True)),
            sin_adjunto=Count('id', filter=Q(tiene_adjunto=False))
        ).order_by('-ano')

        if not estadisticas.exists():
            self.stdout.write(self.style.WARNING("No hay registros en la base de datos."))
            return

        # Encabezado de la tabla
        separador = "+" + "-" * 10 + "+" + "-" * 14 + "+" + "-" * 16 + "+" + "-" * 16 + "+" + "-" * 16 + "+"
        formato_fila = "| {:^8} | {:>12} | {:>14} | {:>14} | {:>13.2f}% |"

        self.stdout.write(separador)
        self.stdout.write("| {:^8} | {:^12} | {:^14} | {:^14} | {:^14} |".format(
            "Año", "Total", "Con Adjunto", "Sin Adjunto", "% Digitalizado"
        ))
        self.stdout.write(separador)

        gran_total = 0
        gran_con_adjunto = 0
        gran_sin_adjunto = 0

        for fila in estadisticas:
            ano = fila['ano'] or 'S/D'
            total = fila['total']
            con_adjunto = fila['con_adjunto']
            sin_adjunto = fila['sin_adjunto']
            porcentaje = (con_adjunto / total * 100) if total > 0 else 0.0

            gran_total += total
            gran_con_adjunto += con_adjunto
            gran_sin_adjunto += sin_adjunto

            self.stdout.write(formato_fila.format(str(ano), total, con_adjunto, sin_adjunto, porcentaje))

        # Fila de totales generales
        gran_porcentaje = (gran_con_adjunto / gran_total * 100) if gran_total > 0 else 0.0
        self.stdout.write(separador)
        self.stdout.write("| {:^8} | {:>12} | {:>14} | {:>14} | {:>13.2f}% |".format(
            "TOTAL", gran_total, gran_con_adjunto, gran_sin_adjunto, gran_porcentaje
        ))
        self.stdout.write(separador)

