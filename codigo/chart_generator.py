from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

from matplotlib.figure import Figure

from models import Circunscripcion, EleccionCongreso2023


class ChartGenerator:
    def build_votes_chart(self, circunscripcion_a: Circunscripcion, circunscripcion_b: Circunscripcion) -> Figure:
        figure = Figure(figsize=(7, 4), dpi=100)
        axis = figure.add_subplot(111)
        nombres = [circunscripcion_a.nombre, circunscripcion_b.nombre]
        votos = [circunscripcion_a.total_votos_validos_calculado, circunscripcion_b.total_votos_validos_calculado]
        axis.bar(nombres, votos, color=["#2fa572", "#f39c12"])
        axis.set_title("Comparativa de votos validos")
        axis.set_ylabel("Votos")
        figure.tight_layout()
        return figure

    def build_seats_chart(self, circunscripcion_a: Circunscripcion, circunscripcion_b: Circunscripcion) -> Figure:
        figure = Figure(figsize=(7, 4), dpi=100)
        axis = figure.add_subplot(111)
        nombres = [circunscripcion_a.nombre, circunscripcion_b.nombre]
        escanos = [circunscripcion_a.total_escanos_calculados, circunscripcion_b.total_escanos_calculados]
        axis.bar(nombres, escanos, color=["#7b61ff", "#ff6b6b"])
        axis.set_title("Comparativa de escaños calculados")
        axis.set_ylabel("Escaños")
        figure.tight_layout()
        return figure

    def build_party_votes_chart(self, election: EleccionCongreso2023, limit: int = 10) -> Figure:
        resumen = election.obtener_resumen_nacional_por_partido()[0:limit]
        etiquetas: List[str] = []
        valores: List[int] = []
        for item in resumen:
            sigla = str(item.get("sigla") or "").strip()
            etiqueta = sigla if sigla != "" else str(item.get("nombre") or "").strip()
            etiquetas.append(etiqueta)
            valores.append(int(item["votos"]))

        figure = Figure(figsize=(7, 4), dpi=100)
        axis = figure.add_subplot(111)
        axis.bar(etiquetas, valores, color="#1f6aa5")
        axis.set_title("Ranking nacional por votos")
        axis.set_ylabel("Votos")
        axis.tick_params(axis="x", rotation=30)
        figure.tight_layout()
        return figure

    def build_circunscription_seats_chart(self, circunscripcion: Circunscripcion) -> Figure:
        resultados = circunscripcion.obtener_resultados_ordenados_por_votos()
        etiquetas: List[str] = []
        valores: List[int] = []
        for resultado in resultados:
            if resultado.escanos_calculados > 0:
                etiquetas.append(resultado.partido.get_identificador_presentacion())
                valores.append(resultado.escanos_calculados)

        figure = Figure(figsize=(7, 4), dpi=100)
        axis = figure.add_subplot(111)
        if len(valores) == 0:
            axis.text(0.5, 0.5, "Sin escaños calculados", ha="center", va="center")
            axis.axis("off")
        else:
            axis.pie(valores, labels=etiquetas, autopct="%1.0f")
            axis.set_title("Distribucion de escaños calculados en {0}".format(circunscripcion.nombre))
        figure.tight_layout()
        return figure

    def build_circunscription_comparison_chart(self, election: EleccionCongreso2023, codigo_a: str, codigo_b: str) -> Figure:
        circ_a = election.circunscripciones[codigo_a]
        circ_b = election.circunscripciones[codigo_b]
        return self.build_votes_chart(circ_a, circ_b)

    def build_distribution_chart(
        self,
        title: str,
        labels: Sequence[str],
        values: Sequence[int],
        ylabel: str,
        limit: int = 8,
    ) -> Figure:
        trimmed_labels, trimmed_values = self._trim_series(labels, values, limit)
        figure = Figure(figsize=(9, 3.8), dpi=100)
        pie_axis = figure.add_subplot(121)
        bar_axis = figure.add_subplot(122)

        if len(trimmed_values) == 0 or sum(trimmed_values) <= 0:
            pie_axis.text(0.5, 0.5, "Sin datos", ha="center", va="center")
            pie_axis.axis("off")
            bar_axis.text(0.5, 0.5, "Sin datos", ha="center", va="center")
            bar_axis.axis("off")
            figure.tight_layout()
            return figure

        colors = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
            "#bcbd22",
            "#17becf",
        ]
        pie_axis.pie(trimmed_values, labels=trimmed_labels, autopct="%1.1f%%", startangle=90, colors=colors[: len(trimmed_values)])
        pie_axis.set_title(title + " · sectores")
        bar_axis.bar(trimmed_labels, trimmed_values, color=colors[: len(trimmed_values)])
        bar_axis.set_title(title + " · barras")
        bar_axis.set_ylabel(ylabel)
        bar_axis.tick_params(axis="x", rotation=35)
        figure.tight_layout()
        return figure

    def _trim_series(self, labels: Sequence[str], values: Sequence[int], limit: int) -> Tuple[List[str], List[int]]:
        safe_limit = max(int(limit), 1)
        pairs = [(str(label), int(value)) for label, value in zip(labels, values) if int(value) > 0]
        pairs.sort(key=lambda item: (-item[1], item[0]))
        if len(pairs) <= safe_limit:
            return [item[0] for item in pairs], [item[1] for item in pairs]
        if safe_limit == 1:
            others_total = sum(item[1] for item in pairs)
            return ["Otros"], [others_total]
        visible = pairs[: safe_limit - 1]
        others_total = 0
        for _, value in pairs[safe_limit - 1 :]:
            others_total = others_total + value
        visible.append(("Otros", others_total))
        return [item[0] for item in visible], [item[1] for item in visible]
