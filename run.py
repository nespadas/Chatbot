# run.py

from app.utils.scheduler import start_background_scheduler
from app import create_app


app = create_app()

if __name__ == "__main__":
    start_background_scheduler(app)

    # 3. INICIAR EL SERVIDOR FLASK
    print("Servidor Flask y Scheduler activos.")
    app.run(host='0.0.0.0', port=8000)