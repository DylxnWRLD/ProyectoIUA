import os
import speech_recognition as sr
import pyttsx3
from transformers import pipeline
from datetime import datetime

# ========================
# CONFIGURACIÓN INICIAL
# ========================
r = sr.Recognizer()
r.pause_threshold = 1.5
r.non_speaking_duration = 0.6
r.energy_threshold = 300
r.dynamic_energy_threshold = True

voz = pyttsx3.init()
voz.setProperty('rate', 170)
voz.setProperty('volume', 1.0)

print("Cargando modelo de IA, espera un momento…")

summarizer = pipeline(
    "summarization",
    model="google/mt5-small",
    tokenizer="google/mt5-small"
)

print("Modelo cargado correctamente ✅")

os.makedirs("notas", exist_ok=True)

# ========================
# FUNCIONES DE APOYO
# ========================

def hablar(texto):
    print("🤖:", texto)
    voz.say(texto)
    voz.runAndWait()

def escuchar():
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=0.8)
        print("🎙️ Escuchando comando...")
        audio = r.listen(source)

    try:
        return r.recognize_google(audio, language="es-ES").lower()
    except:
        return ""

def escuchar_nota(terminaciones):
    nota = ""
    hablar("Comienza a dictar tu nota. Cuando quieras terminar, di: terminar nota, finalizar, guardar nota.")
    print("🎙️ Dictado activado...")

    while True:
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source)

        try:
            texto = r.recognize_google(audio, language="es-ES").lower()
            print(f"📝 Dijiste: {texto}")

            if any(t in texto for t in terminaciones):
                hablar("Entendido, terminando la nota.")
                return nota.strip()

            nota += texto + " "

        except:
            pass

def pedir_nombre_archivo():
    """Pide al usuario que diga el nombre del archivo."""
    hablar("¿Qué nombre quieres ponerle a esta nota?")
    nombre = escuchar().strip().replace(" ", "_")
    if not nombre:
        nombre = datetime.now().strftime("nota_%Y%m%d_%H%M%S")
    return nombre

def guardar_archivo(nombre, contenido):
    ruta = f"notas/{nombre}.txt"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido)
    hablar(f"Archivo guardado como {nombre}")

def listar_notas():
    archivos = os.listdir("notas")
    return [a.replace(".txt", "") for a in archivos if a.endswith(".txt")]

def cargar_nota_por_nombre(nombre):
    ruta = f"notas/{nombre}.txt"
    if not os.path.exists(ruta):
        return None
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read()

# ========================
# FUNCIONALIDAD PRINCIPAL
# ========================

def asistente():
    hablar("Hola, soy tu asistente de notas. Di 'graba nota' o 'ayuda'.")

    nota_actual = ""
    resumen_actual = ""

    comandos_cargar_nota = ["abrir nota", "cargar nota", "nota guardada", "leer una nota guardada"]
    comandos_resumir_guardada = ["resumir nota guardada", "resumen de nota guardada"]

    comandos_grabar = ["graba nota", "nueva nota", "dictar nota", "anotar algo"]
    comandos_resumen = ["resumen", "resúmelo", "resumir", "resume la nota"]
    comandos_leer_nota = ["leer nota", "léela", "lee la nota"]
    comandos_leer_resumen = ["lee el resumen", "léeme el resumen"]
    comandos_guardar_nota = ["guardar nota", "salvar nota"]
    comandos_guardar_resumen = ["guardar resumen", "salvar resumen"]
    comandos_ayuda = ["ayuda", "¿qué puedes hacer?", "comandos"]
    comandos_salir = ["salir", "adiós", "cerrar asistente"]

    terminaciones = [
        "terminar nota",
        "finalizar nota",
        "guardar nota",
        "eso es todo",
        "terminar",
        "finalizar",
        "listo"
    ]

    while True:
        comando = escuchar()

        # ---- GRABAR NOTA ----
        if any(c in comando for c in comandos_grabar):
            nota_actual = escuchar_nota(terminaciones)
            if nota_actual:
                hablar("Nota guardada en memoria temporal.")
            else:
                hablar("No pude captar la nota.")

        # ---- GUARDAR NOTA CON NOMBRE DEL USUARIO ----
        elif any(c in comando for c in comandos_guardar_nota):
            if nota_actual:
                nombre = pedir_nombre_archivo()
                guardar_archivo(nombre, nota_actual)
            else:
                hablar("No hay nota para guardar.")

        # ---- LEER NOTA GUARDADA POR NOMBRE ----
        elif any(c in comando for c in comandos_cargar_nota):
            notas = listar_notas()

            if not notas:
                hablar("No tienes notas guardadas.")
                continue

            hablar("Estas son tus notas disponibles:")
            for n in notas:
                hablar(n)

            hablar("¿Cuál deseas abrir?")
            nombre = escuchar().replace(" ", "_")

            contenido = cargar_nota_por_nombre(nombre)

            if contenido:
                hablar("La nota dice:")
                hablar(contenido)
            else:
                hablar("No encontré una nota con ese nombre.")

        # ---- RESUMIR NOTA GUARDADA ----
        elif any(c in comando for c in comandos_resumir_guardada):
            notas = listar_notas()
            if not notas:
                hablar("No tienes notas guardadas.")
                continue

            hablar("¿Cuál nota deseas resumir?")
            for n in notas:
                hablar(n)

            nombre = escuchar().replace(" ", "_")
            contenido = cargar_nota_por_nombre(nombre)

            if not contenido:
                hablar("No encontré esa nota.")
                continue

            hablar("Generando el resumen, espera…")
            resultado = summarizer(contenido, max_length=120, min_length=40, do_sample=False)

            resumen = (
                resultado[0].get("summary_text") or
                resultado[0].get("generated_text") or
                "No pude generar un resumen."
            )

            hablar("Aquí está el resumen:")
            hablar(resumen)

        # ---- RESUMIR NOTA ACTUAL ----
        elif any(c in comando for c in comandos_resumen):
            if nota_actual:
                hablar("Generando el resumen…")
                resultado = summarizer(nota_actual, max_length=120, min_length=40, do_sample=False)
                resumen_actual = (
                    resultado[0].get("summary_text") or
                    resultado[0].get("generated_text") or
                    "No pude generar el resumen."
                )
                hablar(resumen_actual)
            else:
                hablar("Primero graba una nota.")

        # ---- AYUDA ----
        elif any(c in comando for c in comandos_ayuda):
            hablar("Puedo grabar notas, guardarlas, abrir notas guardadas, resumirlas o salir.")

        # ---- SALIR ----
        elif any(c in comando for c in comandos_salir):
            hablar("Hasta luego.")
            break

        elif comando != "":
            hablar("No entendí ese comando. Di 'ayuda' para ver opciones.")

# ========================
# EJECUCIÓN
# ========================
if __name__ == "__main__":
    asistente()
