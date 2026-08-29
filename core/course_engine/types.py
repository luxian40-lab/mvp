"""Tipos compartidos del Course Engine (storyboard, escenas, runs)."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Optional


class SceneType(str, enum.Enum):
    IMAGEN = 'imagen'
    IMAGEN_ZOOM = 'imagen_zoom'
    DIAGRAMA = 'diagrama'
    VIDEO_IA = 'video_ia'
    TEXTO = 'texto'
    NARRACION = 'narracion'
    TRANSICION = 'transicion'
    RESUMEN = 'resumen'


@dataclass
class Scene:
    orden: int
    tipo: SceneType
    titulo: str
    guion: str
    duracion_seg: float = 5.0
    notas_visuales: str = ''
    asset_url: Optional[str] = None
    asset_s3_key: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'orden': self.orden,
            'tipo': self.tipo.value,
            'titulo': self.titulo,
            'guion': self.guion,
            'duracion_seg': self.duracion_seg,
            'notas_visuales': self.notas_visuales,
            'asset_url': self.asset_url,
            'asset_s3_key': self.asset_s3_key,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Scene:
        return cls(
            orden=int(data['orden']),
            tipo=SceneType(data['tipo']),
            titulo=data.get('titulo', ''),
            guion=data.get('guion', ''),
            duracion_seg=float(data.get('duracion_seg', 5)),
            notas_visuales=data.get('notas_visuales', ''),
            asset_url=data.get('asset_url'),
            asset_s3_key=data.get('asset_s3_key'),
            metadata=data.get('metadata') or {},
        )


@dataclass
class Storyboard:
    titulo_leccion: str
    objetivo: str
    escenas: list[Scene]
    modelo_ia: str = 'gpt-4o-mini'

    def to_dict(self) -> dict:
        return {
            'titulo_leccion': self.titulo_leccion,
            'objetivo': self.objetivo,
            'modelo_ia': self.modelo_ia,
            'escenas': [s.to_dict() for s in self.escenas],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Storyboard:
        return cls(
            titulo_leccion=data.get('titulo_leccion', ''),
            objetivo=data.get('objetivo', ''),
            modelo_ia=data.get('modelo_ia', 'gpt-4o-mini'),
            escenas=[Scene.from_dict(s) for s in data.get('escenas', [])],
        )


@dataclass
class LessonDraft:
    titulo: str
    contenido: str
    puntos_clave: list[str]
    rag_chars: int = 0

    def to_dict(self) -> dict:
        return {
            'titulo': self.titulo,
            'contenido': self.contenido,
            'puntos_clave': self.puntos_clave,
            'rag_chars': self.rag_chars,
        }


@dataclass
class LessonAnalysis:
    audiencia: str
    duracion_estimada_min: int
    conceptos: list[str]
    riesgos_pedagogicos: list[str]
    recomendacion_formato: str

    def to_dict(self) -> dict:
        return {
            'audiencia': self.audiencia,
            'duracion_estimada_min': self.duracion_estimada_min,
            'conceptos': self.conceptos,
            'riesgos_pedagogicos': self.riesgos_pedagogicos,
            'recomendacion_formato': self.recomendacion_formato,
        }


@dataclass
class CourseEngineRun:
    run_id: str
    cliente_id: int
    curso_id: int
    brief: str
    lesson: Optional[LessonDraft] = None
    analysis: Optional[LessonAnalysis] = None
    storyboard: Optional[Storyboard] = None
    video_url: Optional[str] = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'run_id': self.run_id,
            'cliente_id': self.cliente_id,
            'curso_id': self.curso_id,
            'brief': self.brief,
            'lesson': self.lesson.to_dict() if self.lesson else None,
            'analysis': self.analysis.to_dict() if self.analysis else None,
            'storyboard': self.storyboard.to_dict() if self.storyboard else None,
            'video_url': self.video_url,
            'errors': self.errors,
        }
