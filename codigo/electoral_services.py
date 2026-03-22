from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from models import Circunscripcion, EleccionCongreso2023, ResultadoPartido


@dataclass
class FunctionChartDefinition:
    title: str
    labels: List[str]
    values: List[int]
    ylabel: str


@dataclass
class FunctionSection:
    numero: int
    enunciado: str
    respuesta: str
    charts: List[FunctionChartDefinition] = field(default_factory=list)


class ValidationService:
    def validate_election(self, election: EleccionCongreso2023) -> List[str]:
        messages: List[str] = []
        for circunscripcion in election.obtener_circunscripciones_ordenadas():
            messages.extend(self.validate_circunscription(circunscripcion))
        if len(messages) == 0:
            messages.append("CONFIRMACION: La validacion general no detecto incidencias.")
        return messages

    def validate_circunscription(self, circunscripcion: Circunscripcion) -> List[str]:
        messages: List[str] = []
        total_votos = circunscripcion.total_votos_validos_calculado
        total_oficial = circunscripcion.votos_totales_candidaturas_oficiales
        if total_oficial is not None:
            if total_votos == total_oficial:
                messages.append(
                    "CONFIRMACION: La suma de votos de {0} coincide con el total oficial ({1}).".format(
                        circunscripcion.nombre, total_oficial
                    )
                )
            else:
                messages.append(
                    "ERROR: La suma de votos de {0} es {1} y no coincide con el total oficial {2}.".format(
                        circunscripcion.nombre, total_votos, total_oficial
                    )
                )
        else:
            messages.append(
                "CONFIRMACION: La circunscripcion {0} no incluye total oficial de votos a candidaturas; se usa el total calculado {1}.".format(
                    circunscripcion.nombre, total_votos
                )
            )

        total_escanos_oficiales = circunscripcion.total_escanos_oficiales
        if total_escanos_oficiales == circunscripcion.escanos_oficiales_totales:
            messages.append(
                "CONFIRMACION: La suma de escaños oficiales por partido en {0} coincide con los {1} escaños de la circunscripcion.".format(
                    circunscripcion.nombre, circunscripcion.escanos_oficiales_totales
                )
            )
        else:
            messages.append(
                "ERROR: Los escaños oficiales por partido en {0} suman {1} y la circunscripcion declara {2}.".format(
                    circunscripcion.nombre, total_escanos_oficiales, circunscripcion.escanos_oficiales_totales
                )
            )

        diferencias = self._build_seat_difference_messages(circunscripcion)
        if len(diferencias) == 0:
            messages.append("CONFIRMACION: Los escaños calculados coinciden con los oficiales en {0}.".format(circunscripcion.nombre))
        else:
            messages.extend(diferencias)
        return messages

    def _build_seat_difference_messages(self, circunscripcion: Circunscripcion) -> List[str]:
        messages: List[str] = []
        for resultado in circunscripcion.obtener_resultados_ordenados_por_votos():
            if resultado.escanos_calculados != resultado.escanos_oficiales:
                messages.append(
                    "ERROR: Diferencia de escaños en {0} para {1}: oficiales={2}, calculados={3}.".format(
                        circunscripcion.nombre,
                        resultado.partido.get_identificador_presentacion(),
                        resultado.escanos_oficiales,
                        resultado.escanos_calculados,
                    )
                )
        return messages


class SeatCalculatorService:
    def __init__(self, threshold_percentage: float = 3.0) -> None:
        self.threshold_percentage = threshold_percentage

    def calculate_for_election(self, election: EleccionCongreso2023) -> List[str]:
        messages: List[str] = []
        for circunscripcion in election.obtener_circunscripciones_ordenadas():
            messages.extend(self.calculate_for_circunscription(circunscripcion))
        return messages

    def calculate_for_circunscription(self, circunscripcion: Circunscripcion) -> List[str]:
        total_votos = circunscripcion.total_votos_validos_calculado
        if total_votos <= 0:
            return ["ERROR: No se pueden recalcular escaños en {0} porque no hay votos validos.".format(circunscripcion.nombre)]

        elegibles: List[ResultadoPartido] = []
        for resultado in circunscripcion.resultados_por_partido.values():
            porcentaje = (float(resultado.votos) / float(total_votos)) * 100.0
            resultado.escanos_calculados = 0
            if porcentaje >= self.threshold_percentage:
                elegibles.append(resultado)

        cocientes: List[Tuple[float, int, str]] = []
        for resultado in elegibles:
            divisor = 1
            while divisor <= circunscripcion.escanos_oficiales_totales:
                cociente = float(resultado.votos) / float(divisor)
                cocientes.append((cociente, resultado.votos, resultado.partido.codigo))
                divisor = divisor + 1

        cocientes.sort(key=lambda item: (-item[0], -item[1], item[2]))
        adjudicaciones = cocientes[0 : circunscripcion.escanos_oficiales_totales]
        for _, _, codigo_partido in adjudicaciones:
            circunscripcion.resultados_por_partido[codigo_partido].escanos_calculados = (
                circunscripcion.resultados_por_partido[codigo_partido].escanos_calculados + 1
            )

        return [
            "CONFIRMACION: Se recalcularon los escaños de {0} mediante D'Hondt con barrera del {1}% sobre votos validos a candidaturas.".format(
                circunscripcion.nombre, self.threshold_percentage
            )
        ]


class StatisticsService:
    def build_report(self, election: EleccionCongreso2023) -> str:
        statistics = self.build_general_statistics(election)
        lines: List[str] = []
        lines.append("RESUMEN GENERAL")
        lines.append("- Circunscripciones: {0}".format(statistics["total_circunscripciones"]))
        lines.append("- Partidos: {0}".format(statistics["total_partidos"]))
        lines.append("- Votos a candidaturas: {0}".format(statistics["total_votos"]))
        lines.append("- Escaños oficiales: {0}".format(statistics["total_escanos_oficiales"]))
        lines.append("- Escaños calculados: {0}".format(statistics["total_escanos_calculados"]))
        lines.append("")
        lines.append("TOP 10 PARTIDOS POR VOTO")
        for index, item in enumerate(statistics["ranking_partidos"][0:10], start=1):
            etiqueta = self._format_party_label(item)
            lines.append(
                "{0}. {1}: {2} votos | {3} escaños oficiales | {4} calculados".format(
                    index, etiqueta, item["votos"], item["escanos_oficiales"], item["escanos_calculados"]
                )
            )

        lines.append("")
        lines.append("ANALISIS TERRITORIAL")
        for item in statistics["resumen_territorial"][0:5]:
            lines.append(
                "- {0}: votos={1}, partidos con votos={2}, escaños oficiales={3}, escaños calculados={4}".format(
                    item["circunscripcion"], item["votos"], item["partidos"], item["escanos_oficiales"], item["escanos_calculados"]
                )
            )

        diferencias = statistics["diferencias"]
        lines.append("")
        lines.append("DIFERENCIAS DE ESCAÑOS")
        if len(diferencias) == 0:
            lines.append("- No se detectaron diferencias entre escaños oficiales y calculados.")
        else:
            for item in diferencias[0:20]:
                lines.append(
                    "- {0} | {1}: oficiales={2}, calculados={3}, diferencia={4}".format(
                        item["circunscripcion"], item["partido"], item["oficiales"], item["calculados"], item["diferencia"]
                    )
                )
        return "\n".join(lines)

    def build_general_statistics(self, election: EleccionCongreso2023) -> Dict[str, object]:
        total_circunscripciones = len(election.circunscripciones)
        total_partidos = len(election.partidos)
        total_votos = 0
        total_escanos_oficiales = 0
        total_escanos_calculados = 0

        for circunscripcion in election.circunscripciones.values():
            total_votos = total_votos + circunscripcion.total_votos_validos_calculado
            total_escanos_oficiales = total_escanos_oficiales + circunscripcion.total_escanos_oficiales
            total_escanos_calculados = total_escanos_calculados + circunscripcion.total_escanos_calculados

        return {
            "total_circunscripciones": total_circunscripciones,
            "total_partidos": total_partidos,
            "total_votos": total_votos,
            "total_escanos_oficiales": total_escanos_oficiales,
            "total_escanos_calculados": total_escanos_calculados,
            "ranking_partidos": election.obtener_resumen_nacional_por_partido(),
            "diferencias": self.build_seat_differences(election),
            "resumen_territorial": self.build_territorial_summary(election),
        }

    def build_seat_differences(self, election: EleccionCongreso2023) -> List[Dict[str, object]]:
        diferencias: List[Dict[str, object]] = []
        for circunscripcion in election.circunscripciones.values():
            for resultado in circunscripcion.resultados_por_partido.values():
                if resultado.diferencia_escanos != 0:
                    diferencias.append(
                        {
                            "circunscripcion": circunscripcion.nombre,
                            "partido": resultado.partido.get_identificador_presentacion(),
                            "oficiales": resultado.escanos_oficiales,
                            "calculados": resultado.escanos_calculados,
                            "diferencia": resultado.diferencia_escanos,
                        }
                    )
        diferencias.sort(key=lambda item: (-abs(int(item["diferencia"])), str(item["circunscripcion"])))
        return diferencias

    def build_territorial_summary(self, election: EleccionCongreso2023) -> List[Dict[str, object]]:
        resumen: List[Dict[str, object]] = []
        for circunscripcion in election.obtener_circunscripciones_ordenadas():
            resumen.append(
                {
                    "circunscripcion": circunscripcion.nombre,
                    "votos": circunscripcion.total_votos_validos_calculado,
                    "partidos": len(circunscripcion.resultados_por_partido),
                    "escanos_oficiales": circunscripcion.total_escanos_oficiales,
                    "escanos_calculados": circunscripcion.total_escanos_calculados,
                }
            )
        resumen.sort(key=lambda item: (-int(item["votos"]), str(item["circunscripcion"])))
        return resumen

    def _format_party_label(self, item: Dict[str, object]) -> str:
        sigla = str(item.get("sigla") or "").strip()
        if sigla != "":
            return sigla
        return str(item.get("nombre") or "").strip()


class FunctionsService:
    def build_sections(self, election: EleccionCongreso2023, circunscripcion_codigo: str, n_value: int) -> List[FunctionSection]:
        circunscripcion = self._get_reference_circunscription(election, circunscripcion_codigo)
        community_summaries = self._build_all_community_summaries(election)
        comunidad = self._build_community_summary(community_summaries, circunscripcion.comunidad_autonoma)
        nacional = self._build_national_summary(election)
        prompts = self._get_prompts()
        builders = {
            1: lambda: self._section_graphs_votes(prompts[0], circunscripcion, comunidad, nacional),
            2: lambda: self._section_null_blank(prompts[1], election, community_summaries),
            3: lambda: self._section_cera_participation(prompts[2], election, community_summaries),
            4: lambda: self._section_parties_exactly_n(prompts[3], election, n_value),
            5: lambda: self._section_cera_population(prompts[4], community_summaries),
            6: lambda: self._section_dhondt(prompts[5], election, circunscripcion),
            7: lambda: self._section_validation(prompts[6], election),
            8: lambda: self._section_graphs_seats(prompts[7], circunscripcion, comunidad, nacional),
            9: lambda: self._section_last_seat(prompts[8], election),
            10: lambda: self._section_cheapest_seats(prompts[9], election),
            11: lambda: self._section_expensive_seats(prompts[10], election),
            12: lambda: self._section_less_votes_for_seat(prompts[11], election),
            13: lambda: self._section_party_without_seat(prompts[12], election),
            14: lambda: self._section_lowest_vote_pairs(prompts[13], election, n_value),
        }
        sections: List[FunctionSection] = []
        for number in range(1, 15):
            section = builders[number]()
            section.numero = number
            sections.append(section)
        return sections

    def _get_prompts(self) -> List[str]:
        return [
            "Represente gráficamente mediante sectores circulares y diagramas de barra los resultados a tres niveles: circunscripción, comunidad y nacional.",
            "Calcule las circunscripciones y CCAA con mayor porcentaje de votos nulos o blanco.",
            "En qué circunscripciones y CCAA hubo mayor participación de votantes CERA (Censo Electoral de españoles Residentes Ausentes).",
            "Dado un número n, devuelva la lista de partidos que se han presentado exactamente en n circunscripciones.",
            "Qué CCAA tienen mayor número de votantes CERA en proporción con el total de su población.",
            "Construya una función que devuelva el número de escaños de cada partido en una circunscripción. Para ello deberá aplicar la regla D’Hondt para el reparto de escaños.",
            "Construya una función que compruebe que los resultados coinciden con los aportados por el Excel.",
            "Al igual que el ejercicio 1 represente gráficamente los resultados de los escaños obtenidos en el congreso a nivel de circunscripción, ccaa y nacional.",
            "Construya una función que nos diga el partido que se quedó con el último escaño asignado en cada circunscripción y el partido que más cerca estuvo de ganar ese escaño y cuántos votos le faltaron para conseguirlo.",
            "Construya una función que responda a la pregunta de qué partidos consiguieron más baratos (necesitaron menos votos) sus escaños, tanto a nivel nacional como de circunscripción.",
            "Construya una función que responda a la pregunta de qué partidos consiguieron más caros (necesitaron más votos) sus escaños, tanto a nivel nacional como de circunscripción.",
            "¿En qué circunscripciones se necesitan menos votos para conseguir un diputado?",
            "¿Cuál fue el partido con más votos que no consiguió escaño?",
            "¿Cuáles fueron las n parejas (partido-circunscripción) con menos votos, pero mayores que cero?",
        ]

    def _section_graphs_votes(self, prompt: str, circ: Circunscripcion, comunidad: Dict[str, object], nacional: Dict[str, object]) -> FunctionSection:
        respuesta = (
            "Se muestran debajo tres visualizaciones de votos a candidaturas: la circunscripción de referencia ({0}), su comunidad autónoma ({1}) y el agregado nacional. "
            "Cada visualización combina sectores circulares y barras.".format(circ.nombre, comunidad["nombre"])
        )
        charts = [
            self._build_chart_definition("Circunscripción · {0}".format(circ.nombre), self._party_items_from_circ(circ, "votos"), "Votos"),
            self._build_chart_definition("Comunidad · {0}".format(comunidad["nombre"]), comunidad["ranking_votos"], "Votos"),
            self._build_chart_definition("Nacional", nacional["ranking_votos"], "Votos"),
        ]
        return FunctionSection(0, prompt, respuesta, charts)

    def _section_null_blank(self, prompt: str, election: EleccionCongreso2023, community_summaries: List[Dict[str, object]]) -> FunctionSection:
        circ_nulos = self._max_ratio_circ(election, lambda c: c.votos_nulos_oficiales or 0, lambda c: c.total_votantes or 0)
        circ_blancos = self._max_ratio_circ(election, lambda c: c.votos_blanco_oficiales or 0, lambda c: c.total_votantes or 0)
        ccaa_nulos = self._max_ratio_community(community_summaries, "votos_nulos_oficiales", "total_votantes")
        ccaa_blancos = self._max_ratio_community(community_summaries, "votos_blanco_oficiales", "total_votantes")
        respuesta = (
            "Mayor porcentaje de votos nulos: circunscripción {0} ({1:.2f}%) y CCAA {2} ({3:.2f}%).\n"
            "Mayor porcentaje de votos en blanco: circunscripción {4} ({5:.2f}%) y CCAA {6} ({7:.2f}%)."
        ).format(circ_nulos[0], circ_nulos[1], ccaa_nulos[0], ccaa_nulos[1], circ_blancos[0], circ_blancos[1], ccaa_blancos[0], ccaa_blancos[1])
        return FunctionSection(0, prompt, respuesta)

    def _section_cera_participation(self, prompt: str, election: EleccionCongreso2023, community_summaries: List[Dict[str, object]]) -> FunctionSection:
        circ = self._max_ratio_circ(election, lambda c: c.total_votantes_cera or 0, lambda c: c.censo_cera or 0)
        ccaa = self._max_ratio_community(community_summaries, "total_votantes_cera", "censo_cera")
        respuesta = (
            "La mayor participación CERA se dio en la circunscripción {0} con un {1:.2f}% del censo CERA y en la CCAA {2} con un {3:.2f}% ."
        ).format(circ[0], circ[1], ccaa[0], ccaa[1])
        return FunctionSection(0, prompt, respuesta)

    def _section_parties_exactly_n(self, prompt: str, election: EleccionCongreso2023, n_value: int) -> FunctionSection:
        appearances: Dict[str, int] = {}
        labels: Dict[str, str] = {}
        for circ in election.circunscripciones.values():
            for codigo, resultado in circ.resultados_por_partido.items():
                appearances[codigo] = appearances.get(codigo, 0) + 1
                labels[codigo] = resultado.partido.get_identificador_presentacion()
        partidos = sorted(labels[codigo] for codigo, total in appearances.items() if total == n_value)
        if len(partidos) == 0:
            respuesta = "No hay partidos presentados exactamente en n={0} circunscripciones.".format(n_value)
        else:
            respuesta = "Partidos presentados exactamente en n={0} circunscripciones:\n- {1}".format(n_value, "\n- ".join(partidos))
        return FunctionSection(0, prompt, respuesta)

    def _section_cera_population(self, prompt: str, community_summaries: List[Dict[str, object]]) -> FunctionSection:
        ratios: List[Tuple[str, float, int, int]] = []
        for comunidad in community_summaries:
            poblacion = int(comunidad.get("poblacion") or 0)
            votantes_cera = int(comunidad.get("total_votantes_cera") or 0)
            if poblacion > 0:
                ratios.append((str(comunidad["nombre"]), (float(votantes_cera) / float(poblacion)) * 100.0, votantes_cera, poblacion))
        ratios.sort(key=lambda item: (-item[1], item[0]))
        if len(ratios) == 0:
            return FunctionSection(0, prompt, "No hay datos suficientes de población y votantes CERA para calcular esta proporción.")
        top = ratios[:10]
        respuesta = "CCAA con mayor número de votantes CERA en proporción con su población:\n- " + "\n- ".join(
            "{0}: {1:.4f}% ({2} votantes CERA sobre {3} habitantes)".format(nombre, ratio, votantes, poblacion)
            for nombre, ratio, votantes, poblacion in top
        )
        return FunctionSection(0, prompt, respuesta)

    def _section_dhondt(self, prompt: str, election: EleccionCongreso2023, circ: Circunscripcion) -> FunctionSection:
        selected_summary: List[str] = []
        for resultado in circ.obtener_resultados_ordenados_por_votos():
            if resultado.escanos_calculados > 0:
                selected_summary.append("{0}={1}".format(resultado.partido.get_identificador_presentacion(), resultado.escanos_calculados))
        lines: List[str] = []
        for circunscripcion in election.obtener_circunscripciones_ordenadas()[:5]:
            resumen = []
            for resultado in circunscripcion.obtener_resultados_ordenados_por_votos():
                if resultado.escanos_calculados > 0:
                    resumen.append("{0}={1}".format(resultado.partido.get_identificador_presentacion(), resultado.escanos_calculados))
            lines.append("{0}: {1}".format(circunscripcion.nombre, ", ".join(resumen) if len(resumen) > 0 else "sin escaños asignados"))
        respuesta = (
            "La función está implementada para todas las circunscripciones. En la circunscripción seleccionada ({0}) el reparto calculado por D'Hondt es: {1}.\n"
            "Ejemplos adicionales:\n- {2}"
        ).format(circ.nombre, ", ".join(selected_summary) if len(selected_summary) > 0 else "sin escaños asignados", "\n- ".join(lines))
        return FunctionSection(0, prompt, respuesta)

    def _section_validation(self, prompt: str, election: EleccionCongreso2023) -> FunctionSection:
        total_checks = 0
        failed_checks = 0
        failed_lines: List[str] = []
        total_circunscripciones = len(election.circunscripciones)
        for circ in election.obtener_circunscripciones_ordenadas():
            checks = self._validate_all_consistency_rules(circ)
            total_checks = total_checks + len(checks)
            for _, ok, detail in checks:
                if not ok:
                    failed_checks = failed_checks + 1
                    failed_lines.append("{0}: {1}".format(circ.nombre, detail))
        if failed_checks == 0:
            respuesta = "Todas las comprobaciones de coherencia del Excel se cumplen: {0} validaciones superadas en {1} circunscripciones.".format(total_checks, total_circunscripciones)
        else:
            respuesta = "Se detectaron {0} incidencias sobre {1} comprobaciones. Primeras diferencias:\n- {2}".format(
                failed_checks, total_checks, "\n- ".join(failed_lines[:20])
            )
        return FunctionSection(0, prompt, respuesta)

    def _section_graphs_seats(self, prompt: str, circ: Circunscripcion, comunidad: Dict[str, object], nacional: Dict[str, object]) -> FunctionSection:
        respuesta = (
            "Se muestran debajo tres visualizaciones de escaños oficiales: la circunscripción de referencia ({0}), su comunidad autónoma ({1}) y el agregado nacional."
        ).format(circ.nombre, comunidad["nombre"])
        charts = [
            self._build_chart_definition("Circunscripción · {0}".format(circ.nombre), self._party_items_from_circ(circ, "escanos_oficiales"), "Escaños"),
            self._build_chart_definition("Comunidad · {0}".format(comunidad["nombre"]), comunidad["ranking_escanos"], "Escaños"),
            self._build_chart_definition("Nacional", nacional["ranking_escanos"], "Escaños"),
        ]
        return FunctionSection(0, prompt, respuesta, charts)

    def _section_last_seat(self, prompt: str, election: EleccionCongreso2023) -> FunctionSection:
        lines: List[str] = []
        for circ in election.obtener_circunscripciones_ordenadas():
            analysis = self._analyze_last_seat(circ)
            if analysis is None:
                continue
            lines.append(
                "{0}: último escaño para {1}; {2} fue el más cercano y necesitaba {3} votos más".format(
                    circ.nombre, analysis["winner"], analysis["challenger"], analysis["votes_missing"]
                )
            )
        if len(lines) == 0:
            return FunctionSection(0, prompt, "No hay datos suficientes para analizar el último escaño asignado.")
        return FunctionSection(0, prompt, "\n".join(lines))

    def _section_cheapest_seats(self, prompt: str, election: EleccionCongreso2023) -> FunctionSection:
        national = self._find_cost_per_seat_national(election, reverse=False)
        territorial = self._find_cost_per_seat_territorial(election, reverse=False)
        if national is None or territorial is None:
            return FunctionSection(0, prompt, "No hay escaños suficientes para calcular el coste por escaño.")
        respuesta = (
            "A nivel nacional, el escaño más barato corresponde a {0} con {1:.2f} votos por escaño.\n"
            "A nivel de circunscripción, el caso más barato es {2} en {3} con {4:.2f} votos por escaño."
        ).format(national[0], national[1], territorial[0], territorial[2], territorial[1])
        return FunctionSection(0, prompt, respuesta)

    def _section_expensive_seats(self, prompt: str, election: EleccionCongreso2023) -> FunctionSection:
        national = self._find_cost_per_seat_national(election, reverse=True)
        territorial = self._find_cost_per_seat_territorial(election, reverse=True)
        if national is None or territorial is None:
            return FunctionSection(0, prompt, "No hay escaños suficientes para calcular el coste por escaño.")
        respuesta = (
            "A nivel nacional, el escaño más caro corresponde a {0} con {1:.2f} votos por escaño.\n"
            "A nivel de circunscripción, el caso más caro es {2} en {3} con {4:.2f} votos por escaño."
        ).format(national[0], national[1], territorial[0], territorial[2], territorial[1])
        return FunctionSection(0, prompt, respuesta)

    def _section_less_votes_for_seat(self, prompt: str, election: EleccionCongreso2023) -> FunctionSection:
        ranking: List[Tuple[str, float]] = []
        for circ in election.obtener_circunscripciones_ordenadas():
            if circ.escanos_oficiales_totales > 0:
                ranking.append((circ.nombre, float(circ.total_votos_validos_calculado) / float(circ.escanos_oficiales_totales)))
        ranking.sort(key=lambda item: (item[1], item[0]))
        if len(ranking) == 0:
            return FunctionSection(0, prompt, "No hay circunscripciones con escaños para calcular votos por diputado.")
        respuesta = "Las circunscripciones donde hacen falta menos votos para conseguir un diputado son:\n- " + "\n- ".join(
            "{0}: {1:.2f} votos por diputado".format(nombre, ratio) for nombre, ratio in ranking[:10]
        )
        return FunctionSection(0, prompt, respuesta)

    def _section_party_without_seat(self, prompt: str, election: EleccionCongreso2023) -> FunctionSection:
        national_candidates = [item for item in election.obtener_resumen_nacional_por_partido() if int(item["escanos_oficiales"]) == 0]
        if len(national_candidates) == 0:
            respuesta = "Todos los partidos con votos lograron al menos un escaño nacional."
        else:
            item = national_candidates[0]
            respuesta = "El partido con más votos que no consiguió escaño fue {0}, con {1} votos a nivel nacional.".format(
                self._label_item(item), item["votos"]
            )
        return FunctionSection(0, prompt, respuesta)

    def _section_lowest_vote_pairs(self, prompt: str, election: EleccionCongreso2023, n_value: int) -> FunctionSection:
        pairs: List[Tuple[int, str, str]] = []
        for circ in election.obtener_circunscripciones_ordenadas():
            for resultado in circ.resultados_por_partido.values():
                if resultado.votos > 0:
                    pairs.append((resultado.votos, resultado.partido.get_identificador_presentacion(), circ.nombre))
        pairs.sort(key=lambda item: (item[0], item[1], item[2]))
        if len(pairs) == 0:
            return FunctionSection(0, prompt, "No hay parejas partido-circunscripción con votos mayores que cero.")
        respuesta = "Tomando n={0}, las parejas con menos votos mayores que cero son:\n- ".format(n_value) + "\n- ".join(
            "{0} en {1}: {2} votos".format(partido, circ, votos) for votos, partido, circ in pairs[:n_value]
        )
        return FunctionSection(0, prompt, respuesta)

    def _build_chart_definition(self, title: str, items: List[Dict[str, object]], ylabel: str) -> FunctionChartDefinition:
        labels = [str(item["label"]) for item in items if int(item["value"]) > 0]
        values = [int(item["value"]) for item in items if int(item["value"]) > 0]
        return FunctionChartDefinition(title=title, labels=labels, values=values, ylabel=ylabel)

    def _party_items_from_circ(self, circ: Circunscripcion, metric: str) -> List[Dict[str, object]]:
        items: List[Dict[str, object]] = []
        for resultado in circ.obtener_resultados_ordenados_por_votos():
            if metric == "votos":
                value = resultado.votos
            else:
                value = resultado.escanos_oficiales
            if value > 0:
                items.append({"label": resultado.partido.get_identificador_presentacion(), "value": value})
        return items

    def _build_national_summary(self, election: EleccionCongreso2023) -> Dict[str, object]:
        ranking_votos: List[Dict[str, object]] = []
        ranking_escanos: List[Dict[str, object]] = []
        for item in election.obtener_resumen_nacional_por_partido():
            ranking_votos.append({"label": self._label_item(item), "value": int(item["votos"])})
            ranking_escanos.append({"label": self._label_item(item), "value": int(item["escanos_oficiales"])})
        ranking_escanos.sort(key=lambda item: (-int(item["value"]), str(item["label"])))
        return {"nombre": "Nacional", "ranking_votos": ranking_votos, "ranking_escanos": ranking_escanos}

    def _build_all_community_summaries(self, election: EleccionCongreso2023) -> List[Dict[str, object]]:
        grouped: Dict[str, Dict[str, object]] = {}
        for circ in election.obtener_circunscripciones_ordenadas():
            comunidad = circ.comunidad_autonoma or "Sin comunidad"
            if comunidad not in grouped:
                grouped[comunidad] = {
                    "nombre": comunidad,
                    "poblacion": 0,
                    "censo_cera": 0,
                    "total_votantes_cera": 0,
                    "total_votantes": 0,
                    "votos_nulos_oficiales": 0,
                    "votos_blanco_oficiales": 0,
                    "parties": {},
                }
            summary = grouped[comunidad]
            summary["poblacion"] = int(summary["poblacion"]) + int(circ.poblacion or 0)
            summary["censo_cera"] = int(summary["censo_cera"]) + int(circ.censo_cera or 0)
            summary["total_votantes_cera"] = int(summary["total_votantes_cera"]) + int(circ.total_votantes_cera or 0)
            summary["total_votantes"] = int(summary["total_votantes"]) + int(circ.total_votantes or 0)
            summary["votos_nulos_oficiales"] = int(summary["votos_nulos_oficiales"]) + int(circ.votos_nulos_oficiales or 0)
            summary["votos_blanco_oficiales"] = int(summary["votos_blanco_oficiales"]) + int(circ.votos_blanco_oficiales or 0)
            parties = summary["parties"]
            for resultado in circ.resultados_por_partido.values():
                codigo = resultado.partido.codigo
                if codigo not in parties:
                    parties[codigo] = {
                        "label": resultado.partido.get_identificador_presentacion(),
                        "votos": 0,
                        "escanos_oficiales": 0,
                    }
                parties[codigo]["votos"] = int(parties[codigo]["votos"]) + resultado.votos
                parties[codigo]["escanos_oficiales"] = int(parties[codigo]["escanos_oficiales"]) + resultado.escanos_oficiales
        results: List[Dict[str, object]] = []
        for summary in grouped.values():
            ranking_votos = [{"label": item["label"], "value": int(item["votos"])} for item in summary["parties"].values()]
            ranking_votos.sort(key=lambda item: (-int(item["value"]), str(item["label"])))
            ranking_escanos = [{"label": item["label"], "value": int(item["escanos_oficiales"])} for item in summary["parties"].values()]
            ranking_escanos.sort(key=lambda item: (-int(item["value"]), str(item["label"])))
            summary["ranking_votos"] = ranking_votos
            summary["ranking_escanos"] = ranking_escanos
            results.append(summary)
        results.sort(key=lambda item: str(item["nombre"]))
        return results

    def _build_community_summary(self, community_summaries: List[Dict[str, object]], comunidad_nombre: str) -> Dict[str, object]:
        for summary in community_summaries:
            if str(summary["nombre"]) == comunidad_nombre:
                return summary
        if len(community_summaries) > 0:
            return community_summaries[0]
        return {"nombre": "Sin comunidad", "ranking_votos": [], "ranking_escanos": []}

    def _get_reference_circunscription(self, election: EleccionCongreso2023, circunscripcion_codigo: str) -> Circunscripcion:
        if circunscripcion_codigo in election.circunscripciones:
            return election.circunscripciones[circunscripcion_codigo]
        return election.obtener_circunscripciones_ordenadas()[0]

    def _label_item(self, item: Dict[str, object]) -> str:
        sigla = str(item.get("sigla") or "").strip()
        if sigla != "":
            return sigla
        return str(item.get("nombre") or "").strip()

    def _max_ratio_circ(self, election: EleccionCongreso2023, numerator, denominator) -> Tuple[str, float]:
        ranking: List[Tuple[str, float]] = []
        for circ in election.obtener_circunscripciones_ordenadas():
            base = int(denominator(circ) or 0)
            top = int(numerator(circ) or 0)
            if base > 0:
                ranking.append((circ.nombre, (float(top) / float(base)) * 100.0))
        if len(ranking) == 0:
            return ("Sin datos", 0.0)
        ranking.sort(key=lambda item: (-item[1], item[0]))
        return ranking[0]

    def _max_ratio_community(self, community_summaries: List[Dict[str, object]], numerator_attr: str, denominator_attr: str) -> Tuple[str, float]:
        ranking: List[Tuple[str, float]] = []
        for summary in community_summaries:
            base = int(summary.get(denominator_attr) or 0)
            top = int(summary.get(numerator_attr) or 0)
            if base > 0:
                ranking.append((str(summary["nombre"]), (float(top) / float(base)) * 100.0))
        if len(ranking) == 0:
            return ("Sin datos", 0.0)
        ranking.sort(key=lambda item: (-item[1], item[0]))
        return ranking[0]

    def _validate_all_consistency_rules(self, circ: Circunscripcion) -> List[Tuple[str, bool, str]]:
        checks: List[Tuple[str, bool, str]] = []
        if circ.votos_totales_candidaturas_oficiales is not None:
            checks.append(("votos_candidaturas", circ.votos_totales_candidaturas_oficiales == circ.total_votos_validos_calculado, "Votos a candidaturas"))
        if circ.votos_validos_oficiales is not None and circ.votos_blanco_oficiales is not None:
            expected = circ.total_votos_validos_calculado + circ.votos_blanco_oficiales
            checks.append(("votos_validos", circ.votos_validos_oficiales == expected, "Votos válidos"))
        if circ.total_votantes is not None and circ.votos_validos_oficiales is not None and circ.votos_nulos_oficiales is not None:
            expected = circ.votos_validos_oficiales + circ.votos_nulos_oficiales
            checks.append(("total_votantes", circ.total_votantes == expected, "Total votantes"))
        if circ.total_censo_electoral is not None and circ.censo_electoral_sin_cera is not None and circ.censo_cera is not None:
            expected = circ.censo_electoral_sin_cera + circ.censo_cera
            checks.append(("censo_total", circ.total_censo_electoral == expected, "Total censo electoral"))
        if circ.total_votantes is not None and circ.total_votantes_cer is not None and circ.total_votantes_cera is not None:
            expected = circ.total_votantes_cer + circ.total_votantes_cera
            checks.append(("votantes_cer_cera", circ.total_votantes == expected, "Total votantes CER + CERA"))
        checks.append(("escanos", circ.total_escanos_oficiales == circ.escanos_oficiales_totales, "Suma de escaños"))
        checks.append(("dhondt", circ.total_escanos_calculados == circ.escanos_oficiales_totales, "Reparto D'Hondt"))
        return checks

    def _analyze_last_seat(self, circ: Circunscripcion) -> Optional[Dict[str, object]]:
        quotients: List[Tuple[float, int, str, int]] = []
        for resultado in circ.resultados_por_partido.values():
            if resultado.votos <= 0:
                continue
            divisor = 1
            while divisor <= max(circ.escanos_oficiales_totales, 1):
                quotients.append((float(resultado.votos) / float(divisor), resultado.votos, resultado.partido.codigo, divisor))
                divisor = divisor + 1
        if len(quotients) < circ.escanos_oficiales_totales or circ.escanos_oficiales_totales <= 0:
            return None
        quotients.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
        last_winning = quotients[circ.escanos_oficiales_totales - 1]
        winner_code = str(last_winning[2])
        threshold = float(last_winning[0])
        winner = circ.resultados_por_partido[winner_code].partido.get_identificador_presentacion()

        best_challenger = "Sin rival"
        best_missing_votes: Optional[int] = None
        for resultado in circ.resultados_por_partido.values():
            if resultado.partido.codigo == winner_code:
                continue
            next_divisor = resultado.escanos_calculados + 1
            required_votes = int(math.floor(threshold * float(next_divisor))) + 1
            missing_votes = max(required_votes - resultado.votos, 0)
            if best_missing_votes is None or missing_votes < best_missing_votes:
                best_missing_votes = missing_votes
                best_challenger = resultado.partido.get_identificador_presentacion()
        return {"winner": winner, "challenger": best_challenger, "votes_missing": best_missing_votes or 0}

    def _find_cost_per_seat_national(self, election: EleccionCongreso2023, reverse: bool) -> Optional[Tuple[str, float]]:
        candidates: List[Tuple[str, float]] = []
        for item in election.obtener_resumen_nacional_por_partido():
            seats = int(item["escanos_oficiales"])
            if seats > 0:
                candidates.append((self._label_item(item), float(item["votos"]) / float(seats)))
        if len(candidates) == 0:
            return None
        candidates.sort(key=lambda item: (item[1], item[0]))
        if reverse:
            candidates.reverse()
        return candidates[0]

    def _find_cost_per_seat_territorial(self, election: EleccionCongreso2023, reverse: bool) -> Optional[Tuple[str, float, str]]:
        candidates: List[Tuple[str, float, str]] = []
        for circ in election.obtener_circunscripciones_ordenadas():
            for resultado in circ.resultados_por_partido.values():
                if resultado.escanos_oficiales > 0:
                    candidates.append(
                        (
                            resultado.partido.get_identificador_presentacion(),
                            float(resultado.votos) / float(resultado.escanos_oficiales),
                            circ.nombre,
                        )
                    )
        if len(candidates) == 0:
            return None
        candidates.sort(key=lambda item: (item[1], item[0], item[2]))
        if reverse:
            candidates.reverse()
        return candidates[0]
