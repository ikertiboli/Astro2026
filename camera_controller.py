"""Controlador de cámara para Astro2026.

Este módulo encapsula completamente el acceso a ``gphoto2`` y expone una API
orientada a dominio para detectar cámara, consultar parámetros y gestionar
captura/descarga de imágenes.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple


class CameraControllerError(Exception):
    """Error base del controlador de cámara."""


class CameraCommandError(CameraControllerError):
    """Error al ejecutar un comando de gphoto2."""


class CameraNotDetectedError(CameraControllerError):
    """Error cuando no se detecta ninguna cámara conectada."""


class CameraValidationError(CameraControllerError):
    """Error de validación de parámetros de cámara."""


class CameraController:
    """Encapsula toda la interacción con ``gphoto2``.

    La clase está estructurada con helpers privados para:
    - ejecutar comandos,
    - resolver rutas de configuración,
    - parsear salidas de gphoto2.

    Esto facilita incorporar nuevos parámetros o nuevas operaciones sin mezclar
    lógica de parsing con lógica de negocio.
    """

    ISO_CONFIG_CANDIDATES = ("/main/imgsettings/iso", "iso")
    APERTURE_CONFIG_CANDIDATES = (
        "/main/capturesettings/f-number",
        "/main/capturesettings/aperture",
        "aperture",
    )
    SHUTTER_CONFIG_CANDIDATES = (
        "/main/capturesettings/shutterspeed",
        "shutterspeed",
    )

    def __init__(
        self,
        usb_mount_path: str = "/mnt/astro",
        gphoto2_binary: str = "gphoto2",
        timeout_seconds: int = 30,
        env: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Inicializa el controlador.

        Args:
            usb_mount_path: Ruta de montaje USB donde se guardarán imágenes.
            gphoto2_binary: Ejecutable de gphoto2 a utilizar.
            timeout_seconds: Timeout por comando de gphoto2.
            env: Variables de entorno extra para la ejecución de comandos.
        """

        self.usb_mount_path = Path(usb_mount_path)
        self.gphoto2_binary = gphoto2_binary
        self.timeout_seconds = timeout_seconds
        self.env = dict(env or {})

        self._last_captured_file: Optional[Dict[str, str]] = None
        self._last_downloaded_path: Optional[Path] = None

    def detect_camera(self) -> bool:
        """Detecta si hay una cámara conectada vía USB.

        Returns:
            ``True`` si se detecta al menos una cámara; ``False`` en caso contrario.
        """

        output = self._run_command(["--auto-detect"])
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("Model") or stripped.startswith("-"):
                continue
            return True
        return False

    def get_available_isos(self) -> List[str]:
        """Obtiene los valores ISO disponibles en la cámara."""

        _, choices = self._resolve_config_with_choices(self.ISO_CONFIG_CANDIDATES)
        return choices

    def get_apertures(self) -> List[str]:
        """Obtiene las aperturas disponibles en la cámara."""

        _, choices = self._resolve_config_with_choices(
            self.APERTURE_CONFIG_CANDIDATES
        )
        return choices

    def get_shutter_speeds(self) -> List[str]:
        """Obtiene las velocidades de obturación disponibles en la cámara."""

        _, choices = self._resolve_config_with_choices(
            self.SHUTTER_CONFIG_CANDIDATES
        )
        return choices

    def set_parameters(self, iso: str, aperture: str, shutter_speed: str) -> None:
        """Configura ISO, apertura y velocidad de obturación.

        Raises:
            CameraNotDetectedError: Si no hay cámara conectada.
            CameraValidationError: Si algún valor no está disponible.
        """

        self._ensure_camera_connected()

        iso_path, iso_choices = self._resolve_config_with_choices(
            self.ISO_CONFIG_CANDIDATES
        )
        aperture_path, aperture_choices = self._resolve_config_with_choices(
            self.APERTURE_CONFIG_CANDIDATES
        )
        shutter_path, shutter_choices = self._resolve_config_with_choices(
            self.SHUTTER_CONFIG_CANDIDATES
        )

        self._validate_choice("ISO", iso, iso_choices)
        self._validate_choice("Apertura", aperture, aperture_choices)
        self._validate_choice("Velocidad", shutter_speed, shutter_choices)

        self._set_config_value(iso_path, iso)
        self._set_config_value(aperture_path, aperture)
        self._set_config_value(shutter_path, shutter_speed)

    def capture_photo(self) -> Dict[str, str]:
        """Dispara una fotografía en la cámara y guarda su referencia.

        Returns:
            Diccionario con ``folder``, ``number`` y ``filename`` del último archivo.

        Raises:
            CameraNotDetectedError: Si no hay cámara conectada.
            CameraControllerError: Si no se puede localizar el archivo tras disparar.
        """

        self._ensure_camera_connected()
        self._run_command(["--capture-image"])

        latest_file = self._get_latest_file_on_camera()
        if latest_file is None:
            raise CameraControllerError(
                "No se pudo localizar la fotografía recién capturada."
            )

        self._last_captured_file = latest_file
        return latest_file

    def download_image_to_usb(self, filename: Optional[str] = None) -> str:
        """Descarga la última imagen capturada al USB.

        Si no se ha disparado previamente en esta instancia, intenta descargar el
        último archivo disponible en cámara.

        Args:
            filename: Nombre destino opcional; por defecto usa el nombre original.

        Returns:
            Ruta absoluta del archivo descargado.
        """

        self._ensure_camera_connected()

        file_info = self._last_captured_file or self._get_latest_file_on_camera()
        if file_info is None:
            raise CameraControllerError("No hay imágenes disponibles para descargar.")

        self.usb_mount_path.mkdir(parents=True, exist_ok=True)

        target_name = filename or file_info["filename"]
        destination = self._build_safe_destination_path(target_name)

        self._run_command(
            [
                "--folder",
                file_info["folder"],
                "--get-file",
                file_info["number"],
                "--filename",
                str(destination),
            ]
        )

        self._last_downloaded_path = destination
        self._last_captured_file = file_info
        return str(destination)

    def get_settings(self) -> Dict[str, List[str]]:
        """Devuelve opciones actuales de configuración útiles para la UI."""

        return {
            "iso": self.get_available_isos(),
            "apertures": self.get_apertures(),
            "shutter_speeds": self.get_shutter_speeds(),
        }

    def get_last_photo_info(self) -> Dict[str, Any]:
        """Devuelve metadatos conocidos de la última fotografía gestionada."""

        return {
            "camera_file": self._last_captured_file,
            "usb_path": str(self._last_downloaded_path)
            if self._last_downloaded_path
            else None,
        }

    def _ensure_camera_connected(self) -> None:
        """Valida que exista una cámara conectada antes de operar."""

        if not self.detect_camera():
            raise CameraNotDetectedError(
                "No se detectó ninguna cámara. Verifica conexión USB y permisos."
            )

    def _run_command(self, args: List[str]) -> str:
        """Ejecuta gphoto2 y devuelve su salida estándar.

        Raises:
            CameraCommandError: Si el comando falla o expira.
        """

        command = [self.gphoto2_binary] + args
        env = os.environ.copy()
        env.update(self.env)

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
                check=False,
            )
        except FileNotFoundError as exc:
            raise CameraCommandError(
                f"No se encontró el binario de gphoto2: {self.gphoto2_binary}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise CameraCommandError(
                f"Timeout ejecutando comando de cámara: {' '.join(command)}"
            ) from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            detail = stderr or stdout or "Error sin salida"
            raise CameraCommandError(
                f"Comando falló ({result.returncode}): {' '.join(command)} | {detail}"
            )

        return result.stdout

    def _set_config_value(self, config_path: str, value: str) -> None:
        """Aplica un valor a una ruta de configuración de gphoto2."""

        if "=" in config_path:
            raise CameraValidationError(
                f"Ruta de configuración inválida: {config_path}"
            )
        if "=" in value or "\n" in value or "\r" in value or "\x00" in value:
            raise CameraValidationError(
                f"Valor inválido para configuración '{config_path}': {value}"
            )
        self._run_command(["--set-config", f"{config_path}={value}"])

    def _resolve_config_with_choices(
        self, candidates: Tuple[str, ...]
    ) -> Tuple[str, List[str]]:
        """Resuelve una ruta de configuración válida y sus opciones."""

        for candidate in candidates:
            try:
                output = self._run_command(["--get-config", candidate])
                return candidate, self._extract_choices(output)
            except CameraCommandError:
                continue

        raise CameraControllerError(
            f"No se encontró una ruta de configuración válida entre: {candidates}"
        )

    def _extract_choices(self, output: str) -> List[str]:
        """Extrae una lista de opciones a partir de la salida de --get-config."""

        choices: List[str] = []
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped.startswith("Choice:"):
                continue

            # Formato esperado: "Choice: 0 100".
            parts = stripped.split(maxsplit=2)
            if len(parts) == 3:
                choices.append(parts[2])

        return choices

    def _build_safe_destination_path(self, target_name: str) -> Path:
        """Construye una ruta destino evitando path traversal fuera del USB."""

        usb_root = self.usb_mount_path.resolve()
        destination = (usb_root / target_name).resolve()
        try:
            destination.relative_to(usb_root)
        except ValueError as exc:
            raise CameraValidationError(
                f"Nombre de archivo inválido para destino USB: {target_name}"
            ) from exc
        return destination

    def _validate_choice(
        self, label: str, value: str, allowed_values: List[str]
    ) -> None:
        """Valida que el valor elegido esté disponible en cámara."""

        if value not in allowed_values:
            raise CameraValidationError(
                f"{label} '{value}' no disponible. Valores válidos: {allowed_values}"
            )

    def _get_latest_file_on_camera(self) -> Optional[Dict[str, str]]:
        """Obtiene la última imagen listada por gphoto2 en modo recursivo."""

        try:
            output = self._run_command(["--recurse", "--list-files"])
        except CameraCommandError as exc:
            raise CameraControllerError(
                "No se pudo listar archivos en cámara para obtener la última imagen."
            ) from exc

        current_folder = ""
        latest: Optional[Dict[str, str]] = None

        folder_pattern = re.compile(r"folder\s+'([^']+)'", flags=re.IGNORECASE)
        file_pattern = re.compile(r"^#(\d+)\s+(.+?)\s+(?:rd|rw|r-|--)\b")

        for line in output.splitlines():
            folder_match = folder_pattern.search(line)
            if folder_match:
                current_folder = folder_match.group(1)
                continue

            file_match = file_pattern.match(line.strip())
            if file_match and current_folder:
                latest = {
                    "folder": current_folder,
                    "number": file_match.group(1),
                    "filename": file_match.group(2).strip(),
                }

        return latest
