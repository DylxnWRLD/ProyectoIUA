import speech_recognition as sr
import pyttsx3
from transformers import pipeline
from datetime import datetime

# ========================
# CONFIGURACIÓN INICIAL
# ========================
r = sr.Recognizer()
voz = pyttsx3.init()
voz.setProperty('rate', 175)  # velocidad de voz
voz.setProperty('volume', 1.0)

print("Cargando modelo de IA, espera un momento...")
resumidor = pipeline("summarization", model="facebook/bart-large-cnn")
print("Modelo cargado correctamente ✅")

# ========================
# FUNCIONES DE APOYO
# ========================

def hablar(texto):
    """Convierte texto a voz."""
    print("🤖:", texto)
    voz.say(texto)
    voz.runAndWait()

def escuchar():
    """Escucha al usuario y convierte su voz en texto."""
    with sr.Microphone() as source:
        print("\n🎙️ Escuchando...")
        audio = r.listen(source)
    try:
        texto = r.recognize_google(audio, language="es-ES").lower()
        print(f"👉 Dijiste: {texto}")
        return texto
    except sr.UnknownValueError:
        hablar("No te entendí, repite por favor.")
        return ""
    except sr.RequestError:
        hablar("Error con el servicio de reconocimiento.")
        return ""

# ========================
# FUNCIONALIDAD PRINCIPAL
# ========================

def asistente():
    hablar("Hola, soy tu asistente de notas por voz. Di 'graba nota' para comenzar.")
    nota_actual = ""
    resumen_actual = ""

    # Listas de frases equivalentes para cada comando
    comandos_grabar = ["graba nota", "nueva nota", "dictar nota", "anotar algo"]
    comandos_resumen = ["resumen", "resúmelo", "resumir", "hazme un resumen", "resume la nota"]
    comandos_leer_nota = ["léela", "leer nota", "lee la nota", "léeme la nota", "lee lo que escribí"]
    comandos_leer_resumen = ["lee el resumen", "léelo", "léeme el resumen", "lee el resumen generado"]
    comandos_salir = ["salir", "adiós", "terminar", "cerrar asistente", "me voy"]

    while True:
        comando = escuchar()

        # ---- Grabar nota ----
        if any(frase in comando for frase in comandos_grabar):
            hablar("De acuerdo, comienza a dictar tu nota.")
            texto_nota = escuchar()
            if texto_nota:
                nota_actual = texto_nota
                hablar("Nota guardada correctamente.")
            else:
                hablar("No pude escuchar tu nota, intenta de nuevo.")

        # ---- Generar resumen ----
        elif any(frase in comando for frase in comandos_resumen):
            if nota_actual:
                hablar("Generando resumen, espera un momento.")
                resumen = resumidor(nota_actual, max_length=60, min_length=25, do_sample=False)
                resumen_actual = resumen[0]['summary_text']
                hablar("Aquí está el resumen.")
                print("📝 Resumen:", resumen_actual)
                hablar(resumen_actual)
            else:
                hablar("Primero graba una nota antes de resumir.")

        # ---- Leer nota ----
        elif any(frase in comando for frase in comandos_leer_nota):
            if nota_actual:
                hablar("Tu nota dice lo siguiente:")
                hablar(nota_actual)
            else:
                hablar("No tienes ninguna nota grabada.")

        # ---- Leer resumen ----
        elif any(frase in comando for frase in comandos_leer_resumen):
            if resumen_actual:
                hablar("El resumen es:")
                hablar(resumen_actual)
            else:
                hablar("No hay ningún resumen generado todavía.")

        # ---- Salir ----
        elif any(frase in comando for frase in comandos_salir):
            hablar("Hasta luego, Carlos. Fue un gusto ayudarte.")
            break

        # ---- Ningún comando reconocido ----
        elif comando != "":
            hablar("No reconozco ese comando. Puedes decir 'graba nota', 'resumen' o 'salir'.")

# ========================
# EJECUCIÓN
# ========================
if __name__ == "__main__":
    asistente()
