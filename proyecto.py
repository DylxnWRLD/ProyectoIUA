import os
os.environ["HF_HOME"] = "D:/huggingface_cache"

import speech_recognition as sr
import pyttsx3
from transformers import pipeline
from datetime import datetime
import threading

# ========================
# CONFIGURACIÓN INICIAL
# ========================

# Crear carpeta de notas si no existe
if not os.path.exists("notas"):
    os.makedirs("notas")

r = sr.Recognizer()
r.pause_threshold = 1.5
r.non_speaking_duration = 0.6
r.energy_threshold = 300
r.dynamic_energy_threshold = True

voz = pyttsx3.init()
voz.setProperty('rate', 170)
voz.setProperty('volume', 1.0)

# Lock para evitar colisiones de runAndWait()
lock_voz = threading.Lock()

# ========================
# COLA DE VOZ (SOLUCIÓN REAL)
# ========================

cola_voz = []

def motor_voz():
    """Hilo permanente encargado de hablar sin bloquear."""
    while True:
        if cola_voz:
            texto = cola_voz.pop(0)
            with lock_voz:
                try:
                    if voz._inLoop:
                        voz.endLoop()
                except:
                    pass
                voz.say(texto)
                voz.runAndWait()

# hilo permanente
hilo_voz = threading.Thread(target=motor_voz, daemon=True)
hilo_voz.start()


def hablar(texto):
    print("🤖:", texto)
    cola_voz.append(texto)


# 🔥 HABLAR INMEDIATO — sin colisiones
def hablar_inmediato(texto):
    print("🤖:", texto)
    with lock_voz:
        try:
            if voz._inLoop:
                voz.endLoop()
        except:
            pass
        voz.stop()
        voz.say(texto)
        voz.runAndWait()


def hablar_largo(texto, chunk_size=200):
    texto = texto.strip()
    partes = []

    while len(texto) > chunk_size:
        corte = texto.rfind(" ", 0, chunk_size)
        if corte == -1:
            corte = chunk_size
        partes.append(texto[:corte])
        texto = texto[corte:].strip()

    if texto:
        partes.append(texto)

    for p in partes:
        print("🤖:", p)
        cola_voz.append(p)


# ========================
# MODELO RESUMIDOR
# ========================

print("Cargando modelo de IA, espera un momento…")

summarizer = pipeline(
    "summarization",
    model="csebuetnlp/mT5_multilingual_XLSum",
    tokenizer="csebuetnlp/mT5_multilingual_XLSum"
)

print("Modelo cargado correctamente ✅")

def resumir_texto(texto):
    texto = texto.strip()
    tokens = len(texto.split())

    if tokens < 25:
        return texto or ""

    try:
        resultado = summarizer(
            texto,
            max_new_tokens=80,
            do_sample=False
        )
        return resultado[0]["summary_text"]

    except Exception as e:
        print("❌ Error:", e)
        return "No pude generar el resumen."


# ========================
# ESCUCHA
# ========================

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

    # Este mensaje debe sonar sí o sí
    hablar_inmediato(
        "Comienza a dictar tu nota. Cuando quieras terminar, di: terminar nota, finalizar, guardar nota."
    )

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


# ========================
# ARCHIVOS
# ========================

def pedir_nombre_archivo():
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
# ASISTENTE PRINCIPAL
# ========================

def asistente():
    hablar("Hola, soy tu asistente de notas. Di 'graba nota' o 'ayuda'.")

    nota_actual = ""
    resumen_actual = ""

    comandos_cargar_nota = ["abrir nota", "cargar nota", "nota guardada", "leer una nota guardada"]
    comandos_resumir_guardada = ["resumir nota guardada", "resumen de nota guardada"]

    comandos_grabar = ["graba nota", "nueva nota", "dictar nota", "anotar algo"]
    comandos_resumen = ["resumen", "resúmelo", "resumir", "resume la nota"]

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

        # ---- GUARDAR NOTA ----
        elif "guardar nota" in comando:
            if nota_actual:
                nombre = pedir_nombre_archivo()
                guardar_archivo(nombre, nota_actual)
            else:
                hablar("No hay nota para guardar.")

        # ---- ABRIR NOTA ----
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
                hablar_largo(contenido)
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
            resumen = resumir_texto(contenido)

            hablar("Aquí está el resumen:")
            hablar_largo(resumen)

        # ---- RESUMIR NOTA ACTUAL ----
        elif any(c in comando for c in comandos_resumen):
            if nota_actual:
                hablar("Generando el resumen…")
                resumen_actual = resumir_texto(nota_actual)
                hablar_largo(resumen_actual)
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
