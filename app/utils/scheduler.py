# app/utils/scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from .whatsapp_utils import aux_send_whatsapp_response
import atexit


# La función debe aceptar el objeto 'app' de Flask
def start_background_scheduler(flask_app_instance):
    """
    Inicializa, configura y arranca el planificador de tareas.
    """
    scheduler = BackgroundScheduler()

    # --- DEFINICIÓN DE TAREAS ---

    # Tarea Diaria: Ejemplo a las 2:32 AM (hora que falló antes)
    scheduler.add_job(
        func=aux_send_whatsapp_response,  # <<< Usamos el WRAPPER aquí
        trigger='cron',
        hour=11,
        minute=0,
        # ARGUMENTOS: (wa_id, response_text, app_instance)
        # Pasamos la INSTANCIA COMPLETA de Flask como el tercer argumento
        args=('+34656233201', 'Recuerda que siempre has sido mas feliz cuando no has tenido instagram, te quiero', flask_app_instance),
        id='mensaje_diario_232'
    )

    # ... otras tareas ...

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

    return scheduler