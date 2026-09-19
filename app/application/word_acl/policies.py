"""Politicas para la presentacion en documentos Word.

Modulo independiente de politicas de exportacion tabular.
No reutiliza ni hereda de politicas de planillas.
"""

from enum import Enum


class PoliticaPresentacionRevisionWord(str, Enum):
    """Politica de presentacion Word para registros en revision.

    Esta politica es INDEPENDIENTE de cualquier politica de exportacion tabular.
    Gobierna exclusivamente el tratamiento de elementos EN_REVISION.

    REGLA INCONDICIONAL PREVIA:
      Los participantes con estado BLOQUEADO quedan SIEMPRE excluidos de la
      presentacion, de forma incondicional y prioritaria sobre cualquier politica.
      La politica solo aplica a registros EN_REVISION.

    Valores:
      PRESENTAR_CON_OBSERVACION:
        El participante EN_REVISION se contabiliza en las cifras y se emite
        observacion de calidad.
      EXCLUIR_DE_PRESENTACION:
        El participante EN_REVISION se excluye de las cifras cuantitativas
        y se documenta la exclusion en observaciones.
    """

    PRESENTAR_CON_OBSERVACION = "PRESENTAR_CON_OBSERVACION"
    EXCLUIR_DE_PRESENTACION = "EXCLUIR_DE_PRESENTACION"
