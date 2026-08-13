"""Aplicación Flask principal para Astro2026."""

from __future__ import annotations

import threading
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from flask import Flask, Response, jsonify, render_template, request, send_file

from camera_controller import (
    CameraController,
    CameraControllerError,
    CameraNotDetectedError,
)


class AstroApp:
    """Coordina la aplicación web y el controlador de cámara."""

    def __init__(self, camera_controller: CameraController | None = None) -> None:
        """Inicializa la app de dominio con un controlador de cámara."""

        self.camera_controller = camera_controller or CameraController()
        self._lock = threading.RLock()

    def get_settings(self) -> Dict[str, Any]:
        """Obtiene ajustes disponibles para mostrar en la interfaz."""

        with self._lock:
            if not self.camera_controller.detect_camera():
                raise CameraNotDetectedError(
                    "No se detectó ninguna cámara. Verifica conexión USB y permisos."
                )
            return self.camera_controller.get_settings()

    def set_params(self, iso: str, aperture: str, shutter_speed: str) -> None:
        """Aplica parámetros de captura en la cámara."""

        with self._lock:
            self.camera_controller.set_parameters(iso, aperture, shutter_speed)

    def capture(self) -> Dict[str, Any]:
        """Dispara y descarga la última foto al USB."""

        with self._lock:
            camera_file = self.camera_controller.capture_photo()
            usb_path = self.camera_controller.download_image_to_usb()
        return {
            "camera_file": camera_file,
            "usb_path": usb_path,
            "thumbnail_url": "/api/last-photo/image",
        }

    def get_last_photo(self) -> Dict[str, Any]:
        """Devuelve metadatos de la última foto conocida."""

        with self._lock:
            info = self.camera_controller.get_last_photo_info()
            usb_path = info.get("usb_path")
        has_preview = bool(usb_path and _is_previewable_image(Path(usb_path)))
        return {
            **info,
            "thumbnail_url": "/api/last-photo/image" if has_preview else None,
        }


def _parse_set_params_payload(payload: Dict[str, Any]) -> Tuple[str, str, str]:
    """Valida y extrae parámetros obligatorios del payload de configuración."""

    iso = payload.get("iso")
    aperture = payload.get("aperture")
    shutter_speed = payload.get("shutter_speed")

    if not all(isinstance(value, str) and value.strip() for value in (iso, aperture, shutter_speed)):
        raise ValueError("Se requieren 'iso', 'aperture' y 'shutter_speed' como strings no vacíos.")

    return iso.strip(), aperture.strip(), shutter_speed.strip()


def _is_previewable_image(path: Path) -> bool:
    """Indica si el archivo se puede renderizar directamente en un <img>."""

    return path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _guess_image_mimetype(path: Path) -> str:
    """Devuelve mimetype explícito para formatos soportados en previsualización."""

    suffix = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mime_map.get(suffix, "application/octet-stream")


def create_app() -> Flask:
    """Crea la aplicación Flask y registra rutas básicas."""

    app = Flask(__name__)
    astro_app = AstroApp()
    api_token = os.getenv("ASTRO_API_TOKEN", "").strip()

    def _require_api_token() -> Response | None:
        """Valida token de acceso si está configurado en el entorno."""

        if not api_token:
            return None

        provided = request.headers.get("X-API-Token", "")
        if provided != api_token:
            return jsonify({"error": "No autorizado."}), 401
        return None

    @app.get("/")
    def index() -> str:
        """Renderiza la interfaz principal."""

        return render_template("index.html")

    @app.get("/api/settings")
    def api_settings() -> Any:
        """Expone opciones de cámara para ISO, apertura y velocidad."""

        auth_error = _require_api_token()
        if auth_error is not None:
            return auth_error
        try:
            return jsonify(astro_app.get_settings())
        except CameraControllerError:
            return jsonify({"error": "No se pudo obtener la configuración de cámara."}), 503

    @app.post("/api/set-params")
    def api_set_params() -> Any:
        """Configura parámetros de captura solicitados por cliente."""

        auth_error = _require_api_token()
        if auth_error is not None:
            return auth_error
        try:
            payload = request.get_json(silent=True) or {}
            iso, aperture, shutter_speed = _parse_set_params_payload(payload)
            astro_app.set_params(iso, aperture, shutter_speed)
            return jsonify({"status": "ok"})
        except ValueError:
            return (
                jsonify(
                    {
                        "error": "Solicitud inválida: se requieren iso, aperture y shutter_speed."
                    }
                ),
                400,
            )
        except CameraControllerError:
            return jsonify({"error": "No se pudieron aplicar parámetros en cámara."}), 503

    @app.post("/api/capture")
    def api_capture() -> Any:
        """Dispara captura y devuelve metadatos de la última foto."""

        auth_error = _require_api_token()
        if auth_error is not None:
            return auth_error
        try:
            return jsonify(astro_app.capture())
        except CameraControllerError:
            return jsonify({"error": "No se pudo completar la captura de imagen."}), 503

    @app.get("/api/last-photo")
    def api_last_photo() -> Any:
        """Devuelve información de la última foto gestionada."""

        auth_error = _require_api_token()
        if auth_error is not None:
            return auth_error
        return jsonify(astro_app.get_last_photo())

    @app.get("/api/last-photo/image")
    def api_last_photo_image() -> Any:
        """Sirve la última foto descargada al USB para previsualización."""

        auth_error = _require_api_token()
        if auth_error is not None:
            return auth_error
        info = astro_app.get_last_photo()
        usb_path = info.get("usb_path")
        if not usb_path:
            return jsonify({"error": "No hay foto disponible."}), 404

        image_path = Path(usb_path)
        if not image_path.exists() or not image_path.is_file():
            return jsonify({"error": "Archivo no encontrado."}), 404
        usb_root = astro_app.camera_controller.usb_mount_path.resolve()
        try:
            image_path.resolve().relative_to(usb_root)
        except ValueError:
            return jsonify({"error": "Ruta de imagen fuera del almacenamiento USB."}), 400

        if not _is_previewable_image(image_path):
            return (
                jsonify(
                    {
                        "error": "El formato de imagen no es previsualizable en navegador."
                    }
                ),
                415,
            )

        return send_file(image_path, mimetype=_guess_image_mimetype(image_path))

    return app


if __name__ == "__main__":
    # Punto de entrada para ejecutar la aplicación en local.
    create_app().run(host="0.0.0.0", port=5000, debug=False)
