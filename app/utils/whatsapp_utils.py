import logging
import sys
import subprocess
from flask import current_app, jsonify
import json
import requests
import os
import constants as c
import re


PREFIX_SERIE = "serie:"
PREFIX_PELI = "peli:"
PREFIX_LIBRO = "libro:"
PREFIX_JUEGO = "juego:"

PYTHON_W_EXECUTABLE = sys.executable

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )


def generate_response(response):
    # Return text in uppercase
    return response.upper()


def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    try:
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )  # 10 seconds timeout as an example
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except (
        requests.RequestException
    ) as e:  # This will catch any general request exception
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        # Process the response as normal
        log_http_response(response)
        return response

def process_text_for_whatsapp(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    # Substitute the pattern with an empty string
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text

# --- 2. FUNCIÓN DE MANEJO DE SCRIPTS ---

def handle_category_request(message_body, wa_id, name):
    """
    Verifica si el mensaje coincide con un prefijo de categoría y lanza el script correspondiente.

    Retorna una tupla: (str: response_text, bool: is_category_match)
    """

    # Mapeamos los prefijos a sus rutas y tipos de ítem
    category_map = {
        PREFIX_SERIE: {"path": c.PATH_SERIE, "type": "Serie"},
        PREFIX_PELI: {"path": c.PATH_PELICULA, "type": "Película"},
        PREFIX_LIBRO: {"path": c.PATH_LIBRO, "type": "Libro"},
        PREFIX_JUEGO: {"path": c.PATH_GAME, "type": "Juego"},
    }

    message_body_lower = message_body.lower()

    # --- Ejecutable de Python (Asumiendo Windows) ---
    python_executable = sys.executable.replace("python.exe", "pythonw.exe")
    # -----------------------------------------------

    for prefix, info in category_map.items():
        if message_body_lower.startswith(prefix):

            # Extraer el nombre del ítem
            item_name = message_body[len(prefix):].strip()
            script_path = info["path"]
            item_type = info["type"]

            if item_name:
                print(f"Detectada solicitud de {item_type}: {item_name}. Ejecutando script: {script_path}")
                try:
                    # Lanzar el script secundario con el nombre del ítem
                    subprocess.Popen([PYTHON_W_EXECUTABLE, script_path, item_name])

                    response_text = f"¡Perfecto, **{name}**! He iniciado la búsqueda de información para el **{item_type}**: **{item_name}**."

                except Exception as e:
                    print(f"Error al lanzar el script {script_path}: {e}")
                    response_text = f"Disculpa, ha ocurrido un error al iniciar el proceso de búsqueda para el {item_type}."
            else:
                # El usuario solo escribió el prefijo
                response_text = f"¿Qué **{item_type}** estás buscando? Por favor, escribe '{prefix.capitalize()}' seguido del nombre."

            return response_text, True  # Se encontró una coincidencia de categoría

    # No se encontró ningún prefijo de categoría
    return "", False

# --- 3. FUNCIÓN DE ENVÍO DE RESPUESTA ---

def send_whatsapp_response(wa_id, response_text):
    """Crea y envía el mensaje de respuesta de WhatsApp."""
    # current_app debe ser accesible aquí si se usa en get_text_message_input
    data = get_text_message_input(current_app.config["RECIPIENT_WAID"], response_text)
    send_message(data)

# --- 4. FUNCIÓN PRINCIPAL LIMPIA ---

def aux_send_whatsapp_response(wa_id, response_text, app_instance):
    """
    Función auxiliar (wrapper) que ejecuta send_whatsapp_response
    dentro del contexto de la aplicación Flask.
    """
    print(f"DEBUG: Ejecutando tarea programada para {wa_id}...")

    # ------------------- ACCIÓN CLAVE -------------------
    # Crea el contexto de aplicación antes de llamar a la función original
    with app_instance.app_context():
        # Llama a la función original, que ahora encontrará current_app.config
        send_whatsapp_response(wa_id, response_text)
        # ----------------------------------------------------

    print("DEBUG: Envío de mensaje finalizado.")

def process_whatsapp_message(body):
    """
    Procesa el mensaje de WhatsApp entrante, extrayendo datos y determinando la acción.
    """

    # 1. Extracción de Datos Básicos
    try:
        wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
        name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
        message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    except (KeyError, IndexError):
        print("Error: Estructura del payload de WhatsApp no esperada.")
        return "Error en la estructura del mensaje.", 400

    # 2. Manejo de Mensajes no de Texto
    if message.get("type") != "text":
        return "Mensaje no de texto procesado (ignorado).", 200

    message_body = message["text"]["body"].strip()

    # 3. Manejo de Categorías (Serie, Peli, etc.)
    response_text, is_category_match = handle_category_request(message_body, wa_id, name)

    if not is_category_match:
        # 4. Manejo de Mensaje General (si no hubo coincidencia de categoría)
        print("Mensaje normal detectado. Generando respuesta general...")
        response_text = generate_response(message_body)

    # 5. Envío de Respuesta Final
    try:
        send_whatsapp_response(wa_id, response_text)
    except Exception as e:
        print(f"Error al enviar la respuesta de WhatsApp: {e}")
        return "Error al enviar la respuesta.", 500

    return "OK", 200


def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )
