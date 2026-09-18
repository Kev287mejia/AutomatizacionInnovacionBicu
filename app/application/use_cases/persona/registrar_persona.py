"""Caso de uso CU-PER-01: RegistrarPersona.

Orquesta la incorporación bio-demográfica de una persona en el SSOT.
Consagra formalmente la regla institucional RN-C04:
- La cédula es nullable y se mantiene en estricto None / NULL cuando no se provee.
- Prohibida la invención o asunción de identificadores.
- No ejecuta matching de identidad ni deduplicación.
"""

from app.application.commands.persona_commands import RegistrarPersonaCommand
from app.application.dto.output_dtos import PersonaDetalleDTO
from app.core.models.person import Person
from app.core.ports.persona_repository import IPersonaRepository


class RegistrarPersonaUseCase:
    """Caso de uso para incorporar una persona al SSOT bio-demográfico."""

    def __init__(self, persona_repo: IPersonaRepository) -> None:
        """Inicializa el caso de uso con el repositorio de personas.

        Args:
            persona_repo: Puerto de persistencia del agregado Persona.
        """
        self._persona_repo = persona_repo

    def execute(self, command: RegistrarPersonaCommand) -> PersonaDetalleDTO:
        """Ejecuta el registro de la persona respetando la regla RN-C04.

        Args:
            command: Comando con los datos bio-demográficos.

        Returns:
            PersonaDetalleDTO con los datos persistidos.

        Raises:
            EntityAlreadyExistsError: Si la cédula oficial no nula ya existe para otra persona.
        """
        # Preservar estricto None si no se suministra cédula (RN-C04)
        cedula_valor = (
            command.cedula.strip()
            if command.cedula and command.cedula.strip()
            else None
        )

        persona = Person(
            nombre_completo=command.nombre_completo,
            nombres=command.nombres,
            apellidos=command.apellidos,
            cedula=cedula_valor,
            numero_unico=command.numero_unico,
            otro_id_institucional=command.otro_id_institucional,
            sexo_original=command.sexo_original,
            sexo_fuente=command.sexo_fuente,
            sexo_normalizado=command.sexo_normalizado,
            fecha_nacimiento=command.fecha_nacimiento,
            edad=command.edad,
            etnia=command.etnia,
            telefono=command.telefono,
            departamento_persona=command.departamento_persona,
            municipio_persona=command.municipio_persona,
            discapacidad=command.discapacidad,
            carrera_original=command.carrera_original,
            fuente_origen=command.fuente_origen,
        )

        self._persona_repo.save(persona)

        return PersonaDetalleDTO(
            id_persona_interno=persona.id_persona_interno,
            nombre_completo=persona.nombre_completo,
            nombres=persona.nombres,
            apellidos=persona.apellidos,
            cedula=persona.cedula,
            numero_unico=persona.numero_unico,
            otro_id_institucional=persona.otro_id_institucional,
            sexo_normalizado=persona.sexo_normalizado,
            fecha_nacimiento=str(persona.fecha_nacimiento) if persona.fecha_nacimiento else None,
            edad=persona.edad,
            etnia=persona.etnia,
            telefono=persona.telefono,
            departamento_persona=persona.departamento_persona,
            municipio_persona=persona.municipio_persona,
            discapacidad=persona.discapacidad,
            carrera_oficial=persona.carrera_oficial,
        )
