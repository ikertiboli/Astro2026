"""Controlador de cámara basado en gphoto2 para Astro2026."""

from typing import Any, Dict


class CameraController:
    """Gestiona la comunicación con la Canon EOS 500D."""

    def __init__(self) -> None:
        """Inicializa estado base del controlador."""

        pass

    def get_settings(self) -> Dict[str, Any]:
        """Obtiene opciones de configuración disponibles de la cámara."""

        pass

    def set_parameters(self, iso: str, aperture: str, shutter_speed: str) -> None:
        """Establece ISO, apertura y velocidad de obturación."""

        pass

    def capture_photo(self) -> Dict[str, Any]:
        """Captura una foto y prepara información para previsualización."""

        pass

    def get_last_photo_info(self) -> Dict[str, Any]:
        """Devuelve metadatos de la última foto capturada."""

        pass
