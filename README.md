# Astro2026 - Remote Astronomical Camera Control

Sistema de control remoto para fotografía astronómica con Canon EOS 500D desde Raspberry Pi.

## Características

- 🔭 Control remoto de la Canon EOS 500D vía USB
- 📱 Interfaz web responsive para móvil
- ⚙️ Control de ISO, apertura y velocidad de obturación
- 🖼️ Previsualización de thumbnails en tiempo real
- 💾 Almacenamiento en USB pendrive
- 🌐 Acceso vía Tailscale/hotspot

## Requisitos

- Raspberry Pi (3B+ o superior recomendado)
- Canon EOS 500D
- Cable USB para conectar cámara
- USB pendrive para almacenamiento
- Python 3.7+
- gphoto2

## Instalación

### 1. Preparar la Raspberry Pi

```bash
sudo apt-get update
sudo apt-get install python3-pip gphoto2 libgphoto2-dev
```

### 2. Instalar dependencias Python

```bash
git clone https://github.com/ikertiboli/Astro2026.git
cd Astro2026
pip3 install -r requirements.txt
```

### 3. Configurar almacenamiento USB

```bash
sudo mkdir -p /mnt/astro
sudo chown pi:pi /mnt/astro
# Montar USB pendrive
sudo mount /dev/sda1 /mnt/astro
```

### 4. Ejecutar la aplicación

```bash
python3 app.py
```

La interfaz estará disponible en: `http://<IP_RASPBERRY>:5000`

## Configuración automática

Para iniciar automáticamente en cada reinicio:

```bash
sudo cp astro_camera.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable astro_camera
sudo systemctl start astro_camera
```

## API Endpoints

- `GET /` - Interfaz web
- `GET /api/settings` - Obtener opciones de la cámara
- `POST /api/set-params` - Establecer ISO, apertura, velocidad
- `POST /api/capture` - Capturar foto y obtener thumbnail
- `GET /api/last-photo` - Información de última foto

## Uso

1. Conectar la Canon 500D a la Raspberry vía USB
2. Acceder a la interfaz web desde el móvil
3. Seleccionar parámetros (ISO, apertura, velocidad)
4. Presionar "Capture"
5. Ver thumbnail y ajustar parámetros si es necesario

## Estructura del proyecto

```
.
├── app.py                 # Aplicación Flask principal
├── camera_controller.py   # Control de gphoto2
├── templates/
│   └── index.html        # Interfaz web
├── static/
│   ├── style.css
│   └── script.js
├── requirements.txt
├── astro_camera.service  # Configuración systemd
└── README.md
```

## Troubleshooting

### Cámara no detectada

```bash
gphoto2 --auto-detect
```

### Problemas de permisos USB

```bash
sudo usermod -a -G plugdev pi
```

## Licencia

MIT
