from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


class DomainMessageBuilder:
    @staticmethod
    def build_confirmation(message: str) -> str:
        return "CONFIRMACION: " + message

    @staticmethod
    def build_error(message: str) -> str:
        return "ERROR: " + message


@dataclass
class Partido:
    codigo: str
    nombre: str
    sigla: str

    def get_identificador_presentacion(self) -> str:
        return self.sigla.strip() or self.nombre.strip() or self.codigo.strip()


@dataclass
class ResultadoPartido:
    partido: Partido
    votos: int
    escanos_oficiales: int = 0
    escanos_calculados: int = 0

    @property
    def diferencia_escanos(self) -> int:
        return self.escanos_calculados - self.escanos_oficiales

    def obtener_porcentaje_voto(self, total_votos_candidaturas: int) -> float:
        if total_votos_candidaturas <= 0:
            return 0.0
        return (float(self.votos) / float(total_votos_candidaturas)) * 100.0


@dataclass
class Circunscripcion:
    codigo: str
    nombre: str
    provincia: str
    comunidad_autonoma: str
    escanos_oficiales_totales: int
    votos_totales_candidaturas_oficiales: Optional[int] = None
    poblacion: Optional[int] = None
    numero_mesas: Optional[int] = None
    censo_electoral_sin_cera: Optional[int] = None
    censo_cera: Optional[int] = None
    total_censo_electoral: Optional[int] = None
    total_votantes_cer: Optional[int] = None
    total_votantes_cera: Optional[int] = None
    total_votantes: Optional[int] = None
    votos_validos_oficiales: Optional[int] = None
    votos_blanco_oficiales: Optional[int] = None
    votos_nulos_oficiales: Optional[int] = None
    resultados_por_partido: Dict[str, ResultadoPartido] = field(default_factory=dict)

    def agregar_resultado(self, resultado: ResultadoPartido) -> str:
        if resultado.votos <= 0:
            return DomainMessageBuilder.build_confirmation(
                f"Se omitio el resultado de {resultado.partido.get_identificador_presentacion()} en {self.nombre} por tener 0 votos."
            )
        self.resultados_por_partido[resultado.partido.codigo] = resultado
        return DomainMessageBuilder.build_confirmation(
            f"Se registro el resultado de {resultado.partido.get_identificador_presentacion()} en {self.nombre}."
        )

    def obtener_resultados_ordenados_por_votos(self) -> List[ResultadoPartido]:
        resultados = list(self.resultados_por_partido.values())
        resultados.sort(key=lambda r: (-int(r.votos), r.partido.get_identificador_presentacion()))
        return resultados

    @property
    def total_votos_validos_calculado(self) -> int:
        return sum(int(r.votos) for r in self.resultados_por_partido.values())

    @property
    def votos_validos_calculados(self) -> int:
        return self.total_votos_validos_calculado + int(self.votos_blanco_oficiales or 0)

    @property
    def votos_emitidos_calculados(self) -> int:
        return self.votos_validos_calculados + int(self.votos_nulos_oficiales or 0)

    @property
    def total_escanos_oficiales(self) -> int:
        return sum(int(r.escanos_oficiales) for r in self.resultados_por_partido.values())

    @property
    def total_escanos_calculados(self) -> int:
        return sum(int(r.escanos_calculados) for r in self.resultados_por_partido.values())


@dataclass
class EleccionCongreso2023:
    nombre: str
    archivo_origen: str
    partidos: Dict[str, Partido] = field(default_factory=dict)
    circunscripciones: Dict[str, Circunscripcion] = field(default_factory=dict)
    metadatos_columnas: Dict[str, str] = field(default_factory=dict)

    def registrar_partido(self, partido: Partido) -> str:
        if partido.codigo in self.partidos:
            actual = self.partidos[partido.codigo]
            if not actual.nombre and partido.nombre:
                actual.nombre = partido.nombre
            if not actual.sigla and partido.sigla:
                actual.sigla = partido.sigla
            return DomainMessageBuilder.build_confirmation(f"Se reutilizo el partido {partido.codigo}.")
        self.partidos[partido.codigo] = partido
        return DomainMessageBuilder.build_confirmation(f"Se registro el partido {partido.codigo}.")

    def registrar_circunscripcion(self, circunscripcion: Circunscripcion) -> str:
        self.circunscripciones[circunscripcion.codigo] = circunscripcion
        return DomainMessageBuilder.build_confirmation(f"Se registro la circunscripcion {circunscripcion.nombre}.")

    def obtener_circunscripciones_ordenadas(self) -> List[Circunscripcion]:
        items = list(self.circunscripciones.values())
        items.sort(key=lambda c: (c.nombre, c.codigo))
        return items

    def obtener_resumen_nacional_por_partido(self) -> List[Dict[str, object]]:
        resumen: Dict[str, Dict[str, object]] = {}
        for circ in self.circunscripciones.values():
            for resultado in circ.resultados_por_partido.values():
                codigo = resultado.partido.codigo
                if codigo not in resumen:
                    resumen[codigo] = {
                        "codigo": codigo,
                        "nombre": resultado.partido.nombre,
                        "sigla": resultado.partido.sigla,
                        "votos": 0,
                        "escanos_oficiales": 0,
                        "escanos_calculados": 0,
                        "circunscripciones_presentado": 0,
                    }
                item = resumen[codigo]
                item["votos"] += int(resultado.votos)
                item["escanos_oficiales"] += int(resultado.escanos_oficiales)
                item["escanos_calculados"] += int(resultado.escanos_calculados)
                item["circunscripciones_presentado"] += 1
        salida = list(resumen.values())
        salida.sort(key=lambda x: (-int(x["votos"]), str(x["sigla"] or x["nombre"])))
        return salida

    def obtener_resumen_por_comunidad(self) -> List[Dict[str, object]]:
        agregados: Dict[str, Dict[str, object]] = {}
        for circ in self.obtener_circunscripciones_ordenadas():
            nombre = circ.comunidad_autonoma.strip() or "Sin comunidad"
            if nombre not in agregados:
                agregados[nombre] = {
                    "nombre": nombre,
                    "poblacion": 0,
                    "censo_cera": 0,
                    "total_votantes_cera": 0,
                    "total_votantes": 0,
                    "votos_nulos_oficiales": 0,
                    "votos_blanco_oficiales": 0,
                    "ranking_votos": {},
                    "ranking_escanos": {},
                }
            item = agregados[nombre]
            item["poblacion"] += int(circ.poblacion or 0)
            item["censo_cera"] += int(circ.censo_cera or 0)
            item["total_votantes_cera"] += int(circ.total_votantes_cera or 0)
            item["total_votantes"] += int(circ.total_votantes or 0)
            item["votos_nulos_oficiales"] += int(circ.votos_nulos_oficiales or 0)
            item["votos_blanco_oficiales"] += int(circ.votos_blanco_oficiales or 0)
            for resultado in circ.resultados_por_partido.values():
                label = resultado.partido.get_identificador_presentacion()
                item["ranking_votos"][label] = int(item["ranking_votos"].get(label, 0)) + int(resultado.votos)
                item["ranking_escanos"][label] = int(item["ranking_escanos"].get(label, 0)) + int(resultado.escanos_oficiales)
        salida = list(agregados.values())
        salida.sort(key=lambda x: str(x["nombre"]))
        return salida