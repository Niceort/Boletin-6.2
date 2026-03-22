from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from models import Circunscripcion, EleccionCongreso2023, ResultadoPartido


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
            messages.append(
                "CONFIRMACION: Los escaños calculados coinciden con los oficiales en {0}.".format(circunscripcion.nombre)
            )
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
            return [
                "ERROR: No se pueden recalcular escaños en {0} porque no hay votos validos.".format(
                    circunscripcion.nombre
                )
            ]

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
            etiqueta = str(item["sigla"]) if str(item["sigla"]) else str(item["nombre"])
            lines.append(
                "{0}. {1}: {2} votos | {3} escaños oficiales | {4} calculados".format(
                    index,
                    etiqueta,
                    item["votos"],
                    item["escanos_oficiales"],
                    item["escanos_calculados"],
                )
            )

        lines.append("")
        lines.append("ANALISIS TERRITORIAL")
        for item in statistics["resumen_territorial"][0:5]:
            lines.append(
                "- {0}: votos={1}, partidos con votos={2}, escaños oficiales={3}, escaños calculados={4}".format(
                    item["circunscripcion"],
                    item["votos"],
                    item["partidos"],
                    item["escanos_oficiales"],
                    item["escanos_calculados"],
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
                        item["circunscripcion"],
                        item["partido"],
                        item["oficiales"],
                        item["calculados"],
                        item["diferencia"],
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

        resumen_partidos = election.obtener_resumen_nacional_por_partido()
        diferencias = self.build_seat_differences(election)
        resumen_territorial = self.build_territorial_summary(election)

        return {
            "total_circunscripciones": total_circunscripciones,
            "total_partidos": total_partidos,
            "total_votos": total_votos,
            "total_escanos_oficiales": total_escanos_oficiales,
            "total_escanos_calculados": total_escanos_calculados,
            "ranking_partidos": resumen_partidos,
            "diferencias": diferencias,
            "resumen_territorial": resumen_territorial,
        }

    def build_circunscription_comparison(
        self, election: EleccionCongreso2023, circunscripcion_a: str, circunscripcion_b: str
    ) -> Dict[str, object]:
        circ_a = election.circunscripciones[circunscripcion_a]
        circ_b = election.circunscripciones[circunscripcion_b]
        return {
            "circunscripcion_a": circ_a.nombre,
            "circunscripcion_b": circ_b.nombre,
            "votos_a": circ_a.total_votos_validos_calculado,
            "votos_b": circ_b.total_votos_validos_calculado,
            "escanos_a": circ_a.total_escanos_calculados,
            "escanos_b": circ_b.total_escanos_calculados,
            "partidos_a": len(circ_a.resultados_por_partido),
            "partidos_b": len(circ_b.resultados_por_partido),
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


class FunctionsService:
    def build_report(self, election: EleccionCongreso2023) -> str:
        sections: List[str] = []
        sections.append("BOLETIN 6 DE EJERCICIOS (SEMANA DEL 23 DE MARZO)")
        sections.append("")
        sections.append(
            "Enunciado:\nEn el Excel que se acompaña tenemos los resultados de las elecciones generales del año 2023 para la elección del Congreso de los Diputados. En este problema vamos a preparar un software que nos ayude a ser los mejores tertulianos de la TV en la noche electoral con información y datos contrastados."
        )
        sections.append("")
        for index, prompt in enumerate(self._get_prompts(), start=1):
            sections.append("{0}) Enunciado:".format(index))
            sections.append(prompt)
            sections.append("Respuesta:")
            sections.append(self._build_answer(index, election))
            sections.append("")
        return "\n".join(sections).strip()

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

    def _build_answer(self, index: int, election: EleccionCongreso2023) -> str:
        handlers = {
            1: self._answer_graphical_votes,
            2: self._answer_missing_null_blank,
            3: self._answer_missing_cera,
            4: self._answer_parties_exactly_n,
            5: self._answer_missing_population_cera,
            6: self._answer_dhondt_summary,
            7: self._answer_validation_summary,
            8: self._answer_graphical_seats,
            9: self._answer_last_seat,
            10: self._answer_cheapest_seats,
            11: self._answer_most_expensive_seats,
            12: self._answer_lowest_votes_per_seat_circunscriptions,
            13: self._answer_party_most_votes_without_seat,
            14: self._answer_lowest_vote_pairs,
        }
        return handlers[index](election)

    def _answer_graphical_votes(self, election: EleccionCongreso2023) -> str:
        national = election.obtener_resumen_nacional_por_partido()[0:5]
        top_text = ", ".join(
            "{0} ({1} votos)".format(self._label_item(item), item["votos"]) for item in national
        )
        return (
            "La aplicación ya dispone de representación visual en las pestañas Resultados y Graficos. "
            "A nivel nacional, los partidos con más voto son: {0}. "
            "Además, desde el modelo actual se puede agregar por circunscripción y por comunidad autónoma para alimentar esos gráficos; esta pestaña resume los cálculos en texto."
        ).format(top_text)

    def _answer_missing_null_blank(self, _: EleccionCongreso2023) -> str:
        return (
            "No es posible responder con exactitud usando la estructura de datos cargada actualmente, "
            "porque el importador no está leyendo campos de votos nulos ni votos en blanco. "
            "La pestaña Funciones lo deja indicado explícitamente para no inventar datos."
        )

    def _answer_missing_cera(self, _: EleccionCongreso2023) -> str:
        return (
            "No es posible calcularlo con el modelo actual porque no se están cargando columnas de participación CERA por circunscripción o comunidad autónoma."
        )

    def _answer_parties_exactly_n(self, election: EleccionCongreso2023) -> str:
        counts: Dict[int, List[str]] = {}
        appearances: Dict[str, int] = {}
        labels: Dict[str, str] = {}
        for circunscripcion in election.circunscripciones.values():
            for codigo, resultado in circunscripcion.resultados_por_partido.items():
                appearances[codigo] = appearances.get(codigo, 0) + 1
                labels[codigo] = resultado.partido.get_identificador_presentacion()
        for codigo, value in appearances.items():
            counts.setdefault(value, []).append(labels[codigo])
        lines: List[str] = []
        for n in sorted(counts.keys())[0:10]:
            partidos = sorted(counts[n])
            lines.append("n={0}: {1}".format(n, ", ".join(partidos[:12]) + ("..." if len(partidos) > 12 else "")))
        if len(lines) == 0:
            return "No hay partidos cargados."
        return "La función queda resumida por valores de n presentes en el dataset:\n- {0}".format("\n- ".join(lines))

    def _answer_missing_population_cera(self, _: EleccionCongreso2023) -> str:
        return (
            "No es posible calcularlo con precisión porque faltan dos datos en la carga actual: votantes CERA y población total por CCAA."
        )

    def _answer_dhondt_summary(self, election: EleccionCongreso2023) -> str:
        lines: List[str] = []
        for circunscripcion in election.obtener_circunscripciones_ordenadas()[0:5]:
            resumen = []
            for resultado in circunscripcion.obtener_resultados_ordenados_por_votos():
                if resultado.escanos_calculados > 0:
                    resumen.append(
                        "{0}={1}".format(resultado.partido.get_identificador_presentacion(), resultado.escanos_calculados)
                    )
            lines.append("{0}: {1}".format(circunscripcion.nombre, ", ".join(resumen[:8])))
        return (
            "La función está implementada y recalcula los escaños de todas las circunscripciones con D'Hondt y barrera del 3%. "
            "Ejemplos de salida:\n- {0}"
        ).format("\n- ".join(lines))

    def _answer_validation_summary(self, election: EleccionCongreso2023) -> str:
        total = 0
        matching = 0
        mismatches: List[str] = []
        for circunscripcion in election.obtener_circunscripciones_ordenadas():
            total = total + 1
            has_difference = False
            for resultado in circunscripcion.resultados_por_partido.values():
                if resultado.escanos_oficiales != resultado.escanos_calculados:
                    has_difference = True
                    break
            if has_difference:
                mismatches.append(circunscripcion.nombre)
            else:
                matching = matching + 1
        if len(mismatches) == 0:
            return "Los resultados calculados coinciden con los del Excel en las {0} circunscripciones cargadas.".format(total)
        return (
            "Coinciden {0} de {1} circunscripciones. Hay diferencias en: {2}."
        ).format(matching, total, ", ".join(mismatches[:10]))

    def _answer_graphical_seats(self, election: EleccionCongreso2023) -> str:
        national = [item for item in election.obtener_resumen_nacional_por_partido() if int(item["escanos_oficiales"]) > 0][0:5]
        top_text = ", ".join(
            "{0} ({1} escaños)".format(self._label_item(item), item["escanos_oficiales"]) for item in national
        )
        return (
            "La aplicación ya representa visualmente los escaños en Resultados y Graficos. "
            "A nivel nacional destacan: {0}. "
            "La información territorial por circunscripción está disponible y puede agregarse también por comunidad autónoma desde los datos cargados."
        ).format(top_text)

    def _answer_last_seat(self, election: EleccionCongreso2023) -> str:
        lines: List[str] = []
        for circunscripcion in election.obtener_circunscripciones_ordenadas()[0:10]:
            analysis = self._analyze_last_seat(circunscripcion)
            if analysis is None:
                continue
            lines.append(
                "{0}: último escaño para {1}; {2} fue el más cercano y necesitaba {3} votos más".format(
                    circunscripcion.nombre,
                    analysis["winner"],
                    analysis["challenger"],
                    analysis["votes_missing"],
                )
            )
        if len(lines) == 0:
            return "No hay información suficiente para analizar el último escaño."
        return "Resumen de las primeras circunscripciones ordenadas alfabéticamente:\n- {0}".format("\n- ".join(lines))

    def _answer_cheapest_seats(self, election: EleccionCongreso2023) -> str:
        national = self._find_best_cost_per_seat_national(election, reverse=False)
        territorial = self._find_best_cost_per_seat_territorial(election, reverse=False)
        return (
            "A nivel nacional, el escaño más barato corresponde a {0} con {1:.2f} votos por escaño. "
            "A nivel de circunscripción, el caso más barato es {2} en {3} con {4:.2f} votos por escaño."
        ).format(national[0], national[1], territorial[0], territorial[2], territorial[1])

    def _answer_most_expensive_seats(self, election: EleccionCongreso2023) -> str:
        national = self._find_best_cost_per_seat_national(election, reverse=True)
        territorial = self._find_best_cost_per_seat_territorial(election, reverse=True)
        return (
            "A nivel nacional, el escaño más caro corresponde a {0} con {1:.2f} votos por escaño. "
            "A nivel de circunscripción, el caso más caro es {2} en {3} con {4:.2f} votos por escaño."
        ).format(national[0], national[1], territorial[0], territorial[2], territorial[1])

    def _answer_lowest_votes_per_seat_circunscriptions(self, election: EleccionCongreso2023) -> str:
        ranking: List[Tuple[str, float]] = []
        for circunscripcion in election.obtener_circunscripciones_ordenadas():
            if circunscripcion.escanos_oficiales_totales > 0:
                ranking.append(
                    (
                        circunscripcion.nombre,
                        float(circunscripcion.total_votos_validos_calculado) / float(circunscripcion.escanos_oficiales_totales),
                    )
                )
        ranking.sort(key=lambda item: (item[1], item[0]))
        lines = ["{0}: {1:.2f} votos por diputado".format(name, value) for name, value in ranking[0:10]]
        return "Las circunscripciones donde hacen falta menos votos por diputado son:\n- {0}".format("\n- ".join(lines))

    def _answer_party_most_votes_without_seat(self, election: EleccionCongreso2023) -> str:
        national_candidates = [item for item in election.obtener_resumen_nacional_por_partido() if int(item["escanos_oficiales"]) == 0]
        if len(national_candidates) == 0:
            return "Todos los partidos con votos lograron al menos un escaño nacional en los datos cargados."
        item = national_candidates[0]
        return "El partido con más votos sin escaño es {0}, con {1} votos a nivel nacional.".format(self._label_item(item), item["votos"])

    def _answer_lowest_vote_pairs(self, election: EleccionCongreso2023) -> str:
        pairs: List[Tuple[int, str, str]] = []
        for circunscripcion in election.obtener_circunscripciones_ordenadas():
            for resultado in circunscripcion.resultados_por_partido.values():
                if resultado.votos > 0:
                    pairs.append(
                        (
                            resultado.votos,
                            resultado.partido.get_identificador_presentacion(),
                            circunscripcion.nombre,
                        )
                    )
        pairs.sort(key=lambda item: (item[0], item[1], item[2]))
        lines = ["{0} en {1}: {2} votos".format(partido, circ, votos) for votos, partido, circ in pairs[0:10]]
        return "Tomando n=10 como muestra inicial, las parejas con menos votos mayores que cero son:\n- {0}".format("\n- ".join(lines))

    def _label_item(self, item: Dict[str, object]) -> str:
        if str(item["sigla"]):
            return str(item["sigla"])
        return str(item["nombre"])

    def _analyze_last_seat(self, circunscripcion: Circunscripcion) -> Optional[Dict[str, object]]:
        quotients: List[Tuple[float, int, str, int]] = []
        for resultado in circunscripcion.resultados_por_partido.values():
            if resultado.votos <= 0:
                continue
            seats = max(circunscripcion.escanos_oficiales_totales, 1)
            divisor = 1
            while divisor <= seats:
                quotients.append((float(resultado.votos) / float(divisor), resultado.votos, resultado.partido.codigo, divisor))
                divisor = divisor + 1
        if len(quotients) < circunscripcion.escanos_oficiales_totales or circunscripcion.escanos_oficiales_totales <= 0:
            return None
        quotients.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
        cutoff_index = circunscripcion.escanos_oficiales_totales - 1
        last_winning = quotients[cutoff_index]
        winner_code = str(last_winning[2])
        winner = circunscripcion.resultados_por_partido[winner_code]
        threshold = float(last_winning[0])

        best_challenger_name = "Sin rival"
        best_missing_votes: Optional[int] = None
        for resultado in circunscripcion.resultados_por_partido.values():
            next_divisor = resultado.escanos_calculados + 1
            if resultado.partido.codigo == winner_code and resultado.escanos_calculados == last_winning[3]:
                continue
            required_votes = int(math.floor(threshold * float(next_divisor))) + 1
            missing_votes = max(required_votes - resultado.votos, 0)
            if best_missing_votes is None or missing_votes < best_missing_votes:
                best_missing_votes = missing_votes
                best_challenger_name = resultado.partido.get_identificador_presentacion()
        if best_missing_votes is None:
            best_missing_votes = 0
        return {
            "winner": winner.partido.get_identificador_presentacion(),
            "challenger": best_challenger_name,
            "votes_missing": best_missing_votes,
        }

    def _find_best_cost_per_seat_national(self, election: EleccionCongreso2023, reverse: bool) -> Tuple[str, float]:
        candidates: List[Tuple[str, float]] = []
        for item in election.obtener_resumen_nacional_por_partido():
            seats = int(item["escanos_oficiales"])
            if seats > 0:
                candidates.append((self._label_item(item), float(item["votos"]) / float(seats)))
        candidates.sort(key=lambda item: (item[1], item[0]), reverse=reverse)
        return candidates[0]

    def _find_best_cost_per_seat_territorial(self, election: EleccionCongreso2023, reverse: bool) -> Tuple[str, float, str]:
        candidates: List[Tuple[str, float, str]] = []
        for circunscripcion in election.obtener_circunscripciones_ordenadas():
            for resultado in circunscripcion.resultados_por_partido.values():
                if resultado.escanos_oficiales > 0:
                    candidates.append(
                        (
                            resultado.partido.get_identificador_presentacion(),
                            float(resultado.votos) / float(resultado.escanos_oficiales),
                            circunscripcion.nombre,
                        )
                    )
        candidates.sort(key=lambda item: (item[1], item[0], item[2]), reverse=reverse)
        return candidates[0]
